from .extensions import db
from .models import User, Expense, MonthlySummary
from sqlalchemy import func
from datetime import datetime, timedelta
import calendar
import os
import json
import threading
from decimal import Decimal
import google.generativeai as genai
from flask import current_app

CATS = ['Food & Drinks', 'Travel', 'Bills & Utilities', 'Shopping', 'Health', 'Education', 'Groceries', 'Others']

def calculateMonthlySummary(user_id, year, month):
    user = User.query.get(user_id)
    if not user: return None
    from .models import ActiveParserTransaction, ArchiveTransaction

    # LEDGER RULE: Recalculate everything from raw transactions
    # 1. Total Paid
    exp_paid = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.type == 'Paid', Expense.include_in_total == True,
        func.extract('year', Expense.expense_date) == year, func.extract('month', Expense.expense_date) == month
    ).scalar() or Decimal(0)
    apt_paid = db.session.query(func.sum(ActiveParserTransaction.amount)).filter(
        ActiveParserTransaction.user_id == user_id, ActiveParserTransaction.type == 'Paid',
        func.extract('year', ActiveParserTransaction.date) == year, func.extract('month', ActiveParserTransaction.date) == month
    ).scalar() or Decimal(0)
    arc_paid = db.session.query(func.sum(ArchiveTransaction.amount)).filter(
        ArchiveTransaction.user_id == user_id, ArchiveTransaction.type == 'Paid',
        func.extract('year', ArchiveTransaction.date) == year, func.extract('month', ArchiveTransaction.date) == month
    ).scalar() or Decimal(0)
    total_paid = Decimal(str(exp_paid)) + Decimal(str(apt_paid)) + Decimal(str(arc_paid))

    # 2. Total Received
    exp_recv = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.type == 'Received', Expense.include_in_total == True,
        func.extract('year', Expense.expense_date) == year, func.extract('month', Expense.expense_date) == month
    ).scalar() or Decimal(0)
    apt_recv = db.session.query(func.sum(ActiveParserTransaction.amount)).filter(
        ActiveParserTransaction.user_id == user_id, ActiveParserTransaction.type == 'Received',
        func.extract('year', ActiveParserTransaction.date) == year, func.extract('month', ActiveParserTransaction.date) == month
    ).scalar() or Decimal(0)
    arc_recv = db.session.query(func.sum(ArchiveTransaction.amount)).filter(
        ArchiveTransaction.user_id == user_id, ArchiveTransaction.type == 'Received',
        func.extract('year', ArchiveTransaction.date) == year, func.extract('month', ArchiveTransaction.date) == month
    ).scalar() or Decimal(0)
    total_received = Decimal(str(exp_recv)) + Decimal(str(apt_recv)) + Decimal(str(arc_recv))

    # 3. GLOBAL LEDGER TRUTH
    g_exp_recv = db.session.query(func.sum(Expense.amount)).filter(Expense.user_id == user_id, Expense.type == 'Received', Expense.include_in_total == True).scalar() or Decimal(0)
    g_apt_recv = db.session.query(func.sum(ActiveParserTransaction.amount)).filter(ActiveParserTransaction.user_id == user_id, ActiveParserTransaction.type == 'Received').scalar() or Decimal(0)
    g_arc_recv = db.session.query(func.sum(ArchiveTransaction.amount)).filter(ArchiveTransaction.user_id == user_id, ArchiveTransaction.type == 'Received').scalar() or Decimal(0)
    global_income = Decimal(str(g_exp_recv)) + Decimal(str(g_apt_recv)) + Decimal(str(g_arc_recv))
    
    g_exp_paid = db.session.query(func.sum(Expense.amount)).filter(Expense.user_id == user_id, Expense.type == 'Paid', Expense.include_in_total == True).scalar() or Decimal(0)
    g_apt_paid = db.session.query(func.sum(ActiveParserTransaction.amount)).filter(ActiveParserTransaction.user_id == user_id, ActiveParserTransaction.type == 'Paid').scalar() or Decimal(0)
    g_arc_paid = db.session.query(func.sum(ArchiveTransaction.amount)).filter(ArchiveTransaction.user_id == user_id, ArchiveTransaction.type == 'Paid').scalar() or Decimal(0)
    global_expense = Decimal(str(g_exp_paid)) + Decimal(str(g_apt_paid)) + Decimal(str(g_arc_paid))

    current_balance = (user.monthly_income if user.monthly_income else Decimal(0)) + global_income - global_expense
    
    monthly_income = user.monthly_income + total_received
    monthly_savings = monthly_income - total_paid

    # Atomic Update 
    summary = MonthlySummary.query.filter_by(user_id=user_id, year=year, month=month).first()
    if not summary:
        summary = MonthlySummary(user_id=user_id, year=year, month=month)
        db.session.add(summary)

    summary.total_income = monthly_income
    summary.total_expenses = total_paid
    summary.total_savings = monthly_savings
    summary.current_balance = current_balance
    
    now = datetime.utcnow()
    last_day = calendar.monthrange(year, month)[1]
    month_end_date = datetime(year, month, last_day, 23, 59, 59)

    if now > month_end_date:
        summary.goal_status = "ACHIEVED" if monthly_savings >= user.savings_goal else "NOT_ACHIEVED"
    else:
        summary.goal_status = "PENDING"

    db.session.commit()
    return summary

def runMonthlyEvaluation(user_id):
    now = datetime.utcnow()
    calculateMonthlySummary(user_id, now.year, now.month)
    
    prev = now.replace(day=1) - timedelta(days=1)
    calculateMonthlySummary(user_id, prev.year, prev.month)

def generateMicroInvestmentPlan(savingsGoal):
    # Ensure savingsGoal is Decimal
    savingsGoal = Decimal(str(savingsGoal))
    
    # Load percentages from config or env
    try:
        from flask import current_app
        micro_pct = Decimal(current_app.config.get('MICRO_PERCENT', 50))
        safe_pct = Decimal(current_app.config.get('SAFE_PERCENT', 30))
        growth_pct = Decimal(current_app.config.get('GROWTH_PERCENT', 20))
    except:
        micro_pct, safe_pct, growth_pct = Decimal(50), Decimal(30), Decimal(20)

    suggestions = []
    allocation = {}
    tier = "micro"

    if savingsGoal < 1000:
        tier = "micro"
        alloc_micro = savingsGoal
        alloc_safe = Decimal(0)
        alloc_growth = Decimal(0)
    elif savingsGoal < 5000:
        tier = "safe" 
        alloc_micro = (micro_pct / 100) * savingsGoal
        alloc_safe = (safe_pct / 100) * savingsGoal
        alloc_growth = (growth_pct / 100) * savingsGoal
    else:
        tier = "growth"
        alloc_micro = (micro_pct / 100) * savingsGoal
        alloc_safe = (safe_pct / 100) * savingsGoal
        alloc_growth = (growth_pct / 100) * savingsGoal

    alloc_micro = round(alloc_micro)
    alloc_safe = round(alloc_safe)
    alloc_growth = round(alloc_growth)
    
    total_alloc = alloc_micro + alloc_safe + alloc_growth
    diff = savingsGoal - total_alloc
    alloc_micro += diff

    allocation = {
        "micro": float(alloc_micro), "micro_percent": float((alloc_micro/savingsGoal)*100) if savingsGoal > 0 else 0,
        "safe": float(alloc_safe), "safe_percent": float((alloc_safe/savingsGoal)*100) if savingsGoal > 0 else 0,
        "growth": float(alloc_growth), "growth_percent": float((alloc_growth/savingsGoal)*100) if savingsGoal > 0 else 0
    }

    remaining_micro = alloc_micro
    if remaining_micro >= 100:
        # Decimal math for amt
        amt = min(remaining_micro, max(Decimal(100), remaining_micro * Decimal('0.6')))
        amt = round(amt / 10) * 10
        suggestions.append({
            "type": "Digital Gold", "amount": float(amt), "risk": "Low", "image": "gold.png",
            "description": "Safe asset that protects against inflation.", "return_range": "10-12% p.a.",
            "min_amount": 100, "tooltip": "24K Gold 99.9% Purity stored in secure vaults."
        })
        remaining_micro -= amt

    if remaining_micro >= 50:
        amt = remaining_micro
        suggestions.append({
            "type": "Digital Silver", "amount": float(amt), "risk": "Medium", "image": "silver.png",
            "description": "Affordable metal with high industrial demand.", "return_range": "12-15% p.a.",
            "min_amount": 50, "tooltip": "99.9% Purity Silver. Good for small diversification."
        })
        remaining_micro = 0

    if remaining_micro > 0:
         suggestions.append({
            "type": "Piggybank Fund", "amount": float(remaining_micro), "risk": "Low", "image": "piggybank.png",
            "description": "Emergency cash for instant access.", "return_range": "0-3% p.a.",
            "min_amount": 1, "tooltip": "Keep this as digital cash or savings account balance."
        })

    remaining_safe = alloc_safe
    if remaining_safe > 0:
        suggestions.append({
            "type": "Mini RD Plan", "amount": float(remaining_safe), "risk": "Low", "image": "rd.png",
            "description": "Guaranteed returns with bank safety.", "return_range": "6-7.5% p.a.",
            "min_amount": 500, "tooltip": "Recurring Deposit with partner banks."
        })

    remaining_growth = alloc_growth
    if remaining_growth > 0:
        suggestions.append({
            "type": "Index Fund SIP", "amount": float(remaining_growth), "risk": "Medium",
            "image": "sip.png", "description": "Track top 50 companies for long-term wealth.",
            "return_range": "12-16% p.a.", "min_amount": 100, "tooltip": "Nifty 50 Index Fund. Low cost, steady growth."
        })

    return {
        "budget": float(savingsGoal), "tier": tier, "allocation": allocation, "suggestions": suggestions
    }

# --- PRODUCTION AI ENGINE ---

def run_async_ai(f):
    """Decorator to run Gemini tasks in background threads to prevent UI blocking."""
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=f, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
    return wrapper

def get_ai_model():
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key: return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-flash-latest')

@run_async_ai
def categorize_with_ai(expense_id):
    """Module 3: Refines categorization based on merchant name and user history."""
    from backend import db # Avoid circular import
    from backend.models import Expense
    from backend import create_app
    app = create_app()
    with app.app_context():
        exp = Expense.query.get(expense_id)
        if not exp or exp.category != 'Others': return

        model = get_ai_model()
        if not model: return

        prompt = f"Categorize this transaction: '{exp.title}'. Valid categories: {CATS}. Return ONLY the category name."
        try:
            res = model.generate_content(prompt).text.strip()
            if res in CATS:
                exp.ai_category_suggestion = res
                # We don't auto-save per user rules, just suggest
                db.session.commit()
        except: pass

@run_async_ai
def detect_anomalies(user_id, expense_id):
    """Module 6: Enhanced Fraud / Anomaly Intelligence"""
    from backend import db
    from backend.models import Expense, AnomalyWarning
    from backend import create_app
    from sqlalchemy import extract
    app = create_app()
    with app.app_context():
        exp = Expense.query.get(expense_id)
        if not exp or exp.type != 'Paid': return

        now = datetime.utcnow()
        model = get_ai_model()

        # 1. Duplicate Detection Engine
        # Fuzzy match: same amount, same date, similar title
        duplicate_candidate = Expense.query.filter(
            Expense.user_id == user_id,
            Expense.id != exp.id,
            Expense.amount == exp.amount,
            db.func.date(Expense.expense_date) == exp.expense_date.date()
        ).first()

        if duplicate_candidate:
            # Check if titles are similar
            if exp.title.lower() in duplicate_candidate.title.lower() or duplicate_candidate.title.lower() in exp.title.lower():
                reason = "Potential Duplicate Charge"
                ai_explanation = f"We noticed two identical charges of ₹{exp.amount} for '{exp.title}' on {exp.expense_date.strftime('%Y-%m-%d')}. Verify if you accidentally paid twice."
                
                if model:
                    try:
                        prompt = f"System: 'Expense AI' auditor. Task: Write a friendly, 1-sentence warning about a possible duplicate charge of ₹{exp.amount} for '{exp.title}'. Act helpful."
                        ai_explanation = model.generate_content(prompt).text.strip()
                    except: pass
                
                warn = AnomalyWarning(user_id=user_id, expense_id=exp.id, type="DUPLICATE", reason=ai_explanation, amount_diff=0, percentage_spike=0)
                db.session.add(warn)
                db.session.commit()
                return # Stop processing further anomalies for this row

        # 2. Category Spike Detection (Rolling window vs Previous Month)
        # Get total for this category LAST month
        prev_month = now.replace(day=1) - timedelta(days=1)
        prev_total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id, Expense.category == exp.category, Expense.type == 'Paid',
            extract('year', Expense.expense_date) == prev_month.year,
            extract('month', Expense.expense_date) == prev_month.month
        ).scalar() or Decimal('0.0')

        # Get total for this category THIS month (including the new expense)
        curr_total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id, Expense.category == exp.category, Expense.type == 'Paid',
            extract('year', Expense.expense_date) == now.year,
            extract('month', Expense.expense_date) == now.month
        ).scalar() or Decimal('0.0')

        # If previous month had significant spend, check for spikes
        if prev_total > 500:
            diff = curr_total - prev_total
            percentage = (diff / prev_total) * 100
            
            # If current spend is 50% higher than last month's TOTAL spend, it's a spike!
            if percentage > 50 and diff > 1000:
                ai_explanation = f"Your '{exp.category}' spending has surged by {percentage:.0f}% compared to last month. Watch out!"
                if model:
                    try:
                        prompt = f"System: 'Expense AI' auditor. Context: User's {exp.category} spending hit ₹{curr_total}, which is a {percentage:.0f}% spike compared to last month's ₹{prev_total}. The recent trigger was ₹{exp.amount} on '{exp.title}'. Task: Generate a short 1-2 sentence friendly alert explaining the spike and offering a quick tip to curb it."
                        ai_explanation = model.generate_content(prompt).text.strip()
                    except: pass

                warn = AnomalyWarning(
                    user_id=user_id, expense_id=exp.id, type="CATEGORY_SPIKE", 
                    reason=ai_explanation, amount_diff=diff, percentage_spike=percentage
                )
                db.session.add(warn)
                db.session.commit()
                return

        # 3. Absolute Large Expense Check (Fallback)
        avg_spend = db.session.query(func.avg(Expense.amount)).filter_by(user_id=user_id, type='Paid').scalar() or Decimal('0.0')
        if exp.amount > (avg_spend * 5) and exp.amount > 2000:
            ai_explanation = f"Large absolute expense of ₹{exp.amount} detected! Your typical average is ₹{avg_spend:,.0f}."
            if model:
                try:
                    prompt = f"System: 'Expense AI' auditor. Context: User spent ₹{exp.amount} on '{exp.title}', which is 5x higher than their ₹{avg_spend:,.0f} average. Task: Keep it 1 short sentence. Ask them if this was a planned large purchase."
                    ai_explanation = model.generate_content(prompt).text.strip()
                except: pass

            warn = AnomalyWarning(user_id=user_id, expense_id=exp.id, type="LARGE_EXPENSE", reason=ai_explanation, amount_diff=(exp.amount - avg_spend), percentage_spike=0)
            db.session.add(warn); db.session.commit()

@run_async_ai
def generate_spending_insights(user_id, year, month):
    """Module 4: Generates a deep financial report based on monthly summary data."""
    from backend import db
    from backend.models import MonthlySummary, AIReport, Expense
    from backend import create_app
    app = create_app()
    with app.app_context():
        summary = MonthlySummary.query.filter_by(user_id=user_id, year=year, month=month).first()
        if not summary: return

        # Get top categories
        top_cats = db.session.query(Expense.category, func.sum(Expense.amount)).filter_by(user_id=user_id, type='Paid').filter(func.extract('year', Expense.expense_date) == year, func.extract('month', Expense.expense_date) == month).group_by(Expense.category).all()
        
        cat_data = {c: float(s) for c, s in top_cats}
        
        model = get_ai_model()
        if not model: return

        prompt = f"""
        Act as a Professional Fintech AI Coach.
        Analyze this monthly spending data for a user:
        Total Income: ₹{summary.total_income}
        Total Spent: ₹{summary.total_expenses}
        Savings Goal: ₹{summary.total_savings} (Net)
        Category Breakdown: {json.dumps(cat_data)}

        Return a human-readable report with:
        1. Behavior Analysis
        2. Savings Advice
        3. Potential Warnings
        4. Positive Reinforcement
        Use bullet points and emojis. Keep it professional yet encouraging.
        """
        try:
            report_text = model.generate_content(prompt).text
            # Store it
            rep = AIReport.query.filter_by(user_id=user_id, year=year, month=month).first()
            if not rep:
                rep = AIReport(user_id=user_id, year=year, month=month, type="MONTHLY_INSIGHT")
                db.session.add(rep)
            rep.content = report_text
            rep.data_snapshot = cat_data
            db.session.commit()
        except: pass
