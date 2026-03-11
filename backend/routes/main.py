from flask import Blueprint, render_template, session, redirect, url_for, request
import os
from ..extensions import db
from ..models import User, Expense, MonthlySummary
from ..utils import runMonthlyEvaluation
from sqlalchemy import func
import calendar
from datetime import datetime

bp = Blueprint('main', __name__)

@bp.app_context_processor
def inject_ai_status():
    return dict(ai_active=bool(os.getenv('GOOGLE_API_KEY')))

@bp.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    # Check if user exists (session might be stale)
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))
        
    if not user.full_name or user.monthly_income == 0: return redirect(url_for('main.profile'))
    
    runMonthlyEvaluation(session['user_id']) # Pass ID from session (string)
    
    now = datetime.utcnow()
    current_summary = MonthlySummary.query.filter_by(user_id=user.id, year=now.year, month=now.month).first()
    
    past_summaries = MonthlySummary.query.filter(
        MonthlySummary.user_id == user.id,
        db.or_(MonthlySummary.year < now.year, db.and_(MonthlySummary.year == now.year, MonthlySummary.month < now.month))
    ).order_by(MonthlySummary.year.desc(), MonthlySummary.month.desc()).all()

    total_paid = current_summary.total_expenses if current_summary else 0
    # Ledger Truth: Total received from transactions in THIS month
    total_received = db.session.query(func.sum(Expense.amount)).filter_by(user_id=user.id, type='Received', include_in_total=True).filter(func.extract('year', Expense.expense_date) == now.year, func.extract('month', Expense.expense_date) == now.month).scalar() or 0
    
    # Dashboard derives from ledger-calculated summary
    current_balance = current_summary.current_balance if current_summary else user.monthly_income
    
    recent = Expense.query.filter_by(user_id=user.id).order_by(Expense.expense_date.desc()).limit(5).all()
    
    last_completed = MonthlySummary.query.filter(
        MonthlySummary.user_id == user.id,
        MonthlySummary.goal_status != "PENDING"
    ).order_by(MonthlySummary.year.desc(), MonthlySummary.month.desc()).first()

    goal_status = 'pending'
    rem = user.savings_goal - current_balance
    savings_msg = f"Month in progress — Save ₹{rem:,.0f} more to reach your goal! 🚀"
    
    if current_balance >= user.savings_goal and user.savings_goal > 0:
        goal_status = 'achieved'
        savings_msg = "Live Status: Savings Goal Reached! 🥳 Keep this balance until month-end! 🎯"
    
    elif last_completed and last_completed.goal_status == "ACHIEVED":
        pass 

    progress_percent = 0
    if user.savings_goal > 0:
        progress_percent = min(100, max(0, float((current_balance / user.savings_goal) * 100)))

    # MODULE 4: PRODUCTION AI SPENDING INSIGHTS
    from ..models import AIReport, AnomalyWarning
    ai_report = AIReport.query.filter_by(user_id=user.id, year=now.year, month=now.month).first()
    
    # MODULE 6: ANOMALY DETECTION ALERTS
    active_anomalies = AnomalyWarning.query.filter_by(user_id=user.id, is_resolved=False).order_by(AnomalyWarning.created_at.desc()).all()

    # Fallback for small advice if report not generated yet
    ai_insight = ai_report.content if ai_report else "AI is analyzing your spending patterns... check back in a moment! 🤖"

    return render_template('index.html', user=user, total_paid=total_paid, total_received=total_received, 
                           balance=current_balance, recent=recent, goal_status=goal_status, 
                           savings_msg=savings_msg, progress_percent=progress_percent,
                           current_month_name=calendar.month_name[now.month],
                           past_summaries=past_summaries, ai_insight=ai_insight,
                           active_anomalies=active_anomalies)

@bp.route('/api/dashboard/stats')
def dashboard_stats():
    if 'user_id' not in session: return {"error": "Unauthorized"}, 401
    u_id = session['user_id']
    user = User.query.get(u_id)
    now = datetime.utcnow()
    
    # Recalculate to ensure absolute fresh data
    from ..utils import calculateMonthlySummary
    summary = calculateMonthlySummary(u_id, now.year, now.month)
    
    return {
        "total_spent": float(summary.total_expenses),
        "total_income": float(summary.total_income),
        "current_balance": float(summary.current_balance),
        "goal_progress": float((summary.current_balance / user.savings_goal * 100)) if user.savings_goal > 0 else 0
    }

@bp.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    if not user: return redirect(url_for('auth.login')) # Handle stale session
    
    if request.method == 'POST':
        user.full_name = request.form.get('full_name')
        user.monthly_income = float(request.form.get('income'))
        user.savings_goal = float(request.form.get('goal'))
        db.session.commit()
        runMonthlyEvaluation(session['user_id'])
        return redirect(url_for('main.index'))
    return render_template('profile.html', user=user)
