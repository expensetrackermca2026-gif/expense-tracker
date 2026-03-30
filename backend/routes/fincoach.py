from flask import Blueprint, request, session, jsonify
from ..extensions import db
from ..models import User, Expense, MonthlySummary, AIReport, AnomalyWarning, InvestmentPlan
from sqlalchemy import func
from datetime import datetime
import os
import json

bp = Blueprint('fincoach', __name__)

def getUserFinancialContext(userId):
    """
    RAG Step 1: Retrieve comprehensive user financial data from the database.
    Behavior: Always fetches real-time data to ensure fresh context.
    """
    user = User.query.get(userId)
    if not user:
        return None

    now = datetime.utcnow()
    
    # 1. Monthly Summary Data
    summary = MonthlySummary.query.filter_by(
        user_id=userId, year=now.year, month=now.month
    ).first()
    
    # 2. Category Statistics (Current Month)
    cat_rows = (
        db.session.query(Expense.category, func.sum(Expense.amount))
        .filter_by(user_id=userId, type='Paid', include_in_total=True)
        .filter(
            func.extract('year', Expense.expense_date) == now.year,
            func.extract('month', Expense.expense_date) == now.month,
        )
        .group_by(Expense.category)
        .all()
    )
    categories = {cat: float(amt) for cat, amt in cat_rows}
    top_category = max(categories, key=categories.get) if categories else "N/A"

    # 3. Recent Large Transactions (Potential triggers for RAG)
    large_txs = (
        Expense.query.filter_by(user_id=userId, type='Paid')
        .filter(Expense.amount > 2000)
        .order_by(Expense.expense_date.desc())
        .limit(3)
        .all()
    )
    large_tx_list = [{"title": t.title, "amount": float(t.amount), "date": t.expense_date.strftime('%Y-%m-%d')} for t in large_txs]

    # 4. Anomaly Alerts (Factual context for grounding)
    anomalies = AnomalyWarning.query.filter_by(user_id=userId, is_resolved=False).order_by(AnomalyWarning.created_at.desc()).limit(3).all()
    anomaly_list = [f"{a.type}: {a.reason}" for a in anomalies]

    # 5. Investment Plan
    inv_plan = InvestmentPlan.query.filter_by(user_id=userId).order_by(InvestmentPlan.created_at.desc()).first()
    investment_context = inv_plan.advice_text if inv_plan else "No specific investment strategy set yet."

    total_income = float(summary.total_income) if summary else float(user.monthly_income or 0)
    total_spent = float(summary.total_expenses) if summary else 0.0
    savings_goal = float(user.savings_goal or 0)
    balance = float(summary.current_balance) if summary else (total_income - total_spent)
    
    # Calculate progress accurately
    goal_progress = (balance / savings_goal * 100) if savings_goal > 0 else 0

    return {
        "user_name": user.full_name or "User",
        "income": total_income,
        "spent": total_spent,
        "balance": balance,
        "savings_goal": savings_goal,
        "savings_progress": round(goal_progress, 1),
        "top_category": top_category,
        "categories": categories,
        "large_transactions": large_tx_list,
        "anomalies": anomaly_list,
        "investment_plan": investment_context[:600],
    }

# --- PROMPT INJECTION DESIGN ---
def _build_production_system_prompt(ctx: dict) -> str:
    """
    RAG Step 2: Inject structured financial context into the AI context.
    Strictly follows the 'Production Grade' rules.
    """
    cat_summary = ", ".join([f"{k}: ₹{v:,.0f}" for k, v in ctx['categories'].items()]) or "No spending data available."
    anomalies_summary = "\n".join([f"- {a}" for a in ctx['anomalies']]) or "No critical anomalies detected."
    large_tx_summary = "\n".join([f"- {t['title']}: ₹{t['amount']} ({t['date']})" for t in ctx['large_transactions']]) or "None"

    return f"""You are a professional Financial AI Coach.
You ONLY answer questions using the provided User Financial Context.
Never generate assumptions or invent numbers that are not in the context.
If information is missing, clearly state: "I don't have enough data to answer that accurately."

### USER FINANCIAL CONTEXT
- **User**: {ctx['user_name']}
- **Monthly Income**: ₹{ctx['income']:,.0f}
- **Total Spent**: ₹{ctx['spent']:,.0f}
- **Current Balance**: ₹{ctx['balance']:,.0f}
- **Savings Goal**: ₹{ctx['savings_goal']:,.0f}
- **Savings Progress**: {ctx['savings_progress']}%
- **Top Category**: {ctx['top_category']}
- **Spending Details**: {cat_summary}
- **Recent Large Expenses**:
{large_tx_summary}
- **Active Anomalies**:
{anomalies_summary}
- **Investment Plan**: {ctx['investment_plan']}

### STRICT RESPONSE RULES
1. NEVER invent numbers.
2. ONLY use provided context.
3. If data is missing → say: "I don't have enough data."
4. Always reference real metrics.
5. Tone: Be precise, short, and factual. Use a professional financial coaching tone.
6. Refuse non-financial related chatter.

### RESPONSE FORMAT
1. Factual Answer (1-2 sentences)
2. Metric Reference (Quote from context)
3. Actionable Coaching Tip"""

# --- FAILSAFE MODE ---
def _get_failsafe_response(user_message, ctx):
    """Rule-based fallback when the AI engine is unavailable."""
    msg = user_message.lower()
    
    if any(k in msg for k in ["spent", "spending", "overspend", "how doing"]):
        return jsonify({
            'reply': f"Based on your actual data, you've spent ₹{ctx['spent']:,.0f} this month. "
                     f"Your top category is {ctx['top_category']}. You have ₹{ctx['balance']:,.0f} left."
        })
    
    if "save" in msg or "goal" in msg:
        return jsonify({
            'reply': f"You've reached {ctx['savings_progress']}% of your ₹{ctx['savings_goal']:,.0f} goal. "
                     f"To improve, focus on reducing expenses in {ctx['top_category']}."
        })

    return jsonify({
        'reply': f"I'm in failsafe mode, but I can see your balance is ₹{ctx['balance']:,.0f}. "
                 f"Please ask me about your spending or savings specifically."
    })

# --- CHAT ENDPOINT ---
@bp.route('/api/fincoach/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()
    chat_history = data.get('history', [])

    if not user_message:
        return jsonify({'error': 'Empty message'}), 400

    # Retrieve real-time data (RAG Step 1)
    ctx = getUserFinancialContext(session['user_id'])
    if not ctx:
        return jsonify({'reply': "Error: Could not retrieve your financial data."}), 500

    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return _get_failsafe_response(user_message, ctx)

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        # Inject context (RAG Step 2)
        system_prompt = _build_production_system_prompt(ctx)
        
        # Gemini 1.5 Flash - Context Aware Setup
        model = genai.GenerativeModel(
            model_name='models/gemini-flash-latest',
            system_instruction=system_prompt
        )

        history_for_gemini = []
        for msg in chat_history[-6:]:  # Balanced memory Window
            role = 'user' if msg.get('role') == 'user' else 'model'
            history_for_gemini.append({'role': role, 'parts': [msg.get('content', '')]})

        # Generate Response (RAG Step 3)
        chat_session = model.start_chat(history=history_for_gemini)
        response = chat_session.send_message(user_message)
        reply = response.text.strip()

        return jsonify({
            'reply': reply, 
            'context_used': {
                'balance': ctx['balance'],
                'spent': ctx['spent']
            }
        })

    except Exception as e:
        print(f"Chatbot Engine Error: {str(e)}")
        return _get_failsafe_response(user_message, ctx)
