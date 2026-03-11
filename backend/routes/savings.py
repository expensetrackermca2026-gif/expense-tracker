from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from ..extensions import db
from ..models import User, SavingsRecommendation
from decimal import Decimal
from datetime import datetime

bp = Blueprint('savings', __name__)

def calculate_savings_breakdown(income):
    income = Decimal(str(income))
    
    # Adaptive Tier Logic
    if income < 10000:
        savings_rate = Decimal('0.10')
        needs_rate = Decimal('0.60')
        wants_rate = Decimal('0.30')
        explanation = "We recommend a conservative 10% savings rate as you build your financial foundation. Focus on covering essentials first!"
    elif income <= 30000:
        savings_rate = Decimal('0.20')
        needs_rate = Decimal('0.50')
        wants_rate = Decimal('0.30')
        explanation = "The classic 50/30/20 rule is perfect for your income level. It balances living well today with security for tomorrow."
    else:
        savings_rate = Decimal('0.30')
        needs_rate = Decimal('0.45')
        wants_rate = Decimal('0.25')
        explanation = "With your income level, you have a great opportunity to accelerate your wealth building by saving 30%."

    savings_amount = income * savings_rate
    needs_amount = income * needs_rate
    wants_amount = income * wants_rate
    
    # Emergency fund: 3 months of income
    emergency_fund_goal = income * 3
    if savings_amount > 0:
        months_to_reach = float(emergency_fund_goal / savings_amount)
    else:
        months_to_reach = 0

    return {
        "income": float(income),
        "savings": float(savings_amount),
        "needs": float(needs_amount),
        "wants": float(wants_amount),
        "emergency_fund_goal": float(emergency_fund_goal),
        "months_to_reach_goal": round(months_to_reach, 1),
        "explanation": explanation
    }

@bp.route('/savings')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = User.query.get(session['user_id'])
    history = SavingsRecommendation.query.filter_by(user_id=user.id).order_by(SavingsRecommendation.created_at.desc()).all()
    
    return render_template('savings.html', user=user, history=history)

@bp.route('/api/savings/recommend', methods=['POST'])
def recommend():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    income = data.get('income')
    
    if not income or float(income) <= 0:
        return jsonify({"error": "Monthly income must be a positive number."}), 400
    
    breakdown = calculate_savings_breakdown(income)
    
    # Store recommendation
    rec = SavingsRecommendation(
        user_id=session['user_id'],
        monthly_income=Decimal(str(income)),
        recommended_savings=Decimal(str(breakdown['savings'])),
        needs_amount=Decimal(str(breakdown['needs'])),
        wants_amount=Decimal(str(breakdown['wants'])),
        emergency_fund_goal=Decimal(str(breakdown['emergency_fund_goal'])),
        months_to_reach_goal=Decimal(str(breakdown['months_to_reach_goal'])),
        explanation=breakdown['explanation']
    )
    db.session.add(rec)
    db.session.commit()
    
    return jsonify(breakdown)
