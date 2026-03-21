from flask import Blueprint, request, session, jsonify
from ..extensions import db
from ..models import User, Expense, MonthlySummary, AIReport
from sqlalchemy import func
from datetime import datetime
import os
import json

bp = Blueprint('fincoach', __name__)


def _get_financial_context(user_id):
    """Build a structured financial context dict from the user's live data."""
    user = User.query.get(user_id)
    if not user:
        return None

    now = datetime.utcnow()
    summary = MonthlySummary.query.filter_by(
        user_id=user_id, year=now.year, month=now.month
    ).first()

    # Category breakdown for this month
    cat_rows = (
        db.session.query(Expense.category, func.sum(Expense.amount))
        .filter_by(user_id=user_id, type='Paid')
        .filter(
            func.extract('year', Expense.expense_date) == now.year,
            func.extract('month', Expense.expense_date) == now.month,
        )
        .group_by(Expense.category)
        .all()
    )
    categories = {cat: float(amt) for cat, amt in cat_rows}

    # Grab the latest AI spending report text (if any)
    ai_report = AIReport.query.filter_by(
        user_id=user_id, year=now.year, month=now.month
    ).first()
    report_text = ai_report.content if ai_report else "Not yet generated."

    total_income = float(summary.total_income) if summary else float(user.monthly_income or 0)
    total_spent = float(summary.total_expenses) if summary else 0.0
    savings_potential = round(total_income - total_spent, 2)

    return {
        "user_name": user.full_name or "User",
        "monthly_income": total_income,
        "total_spent": total_spent,
        "savings_potential": savings_potential,
        "savings_goal": float(user.savings_goal or 0),
        "categories": categories,
        "ai_report_summary": report_text[:800] if report_text else "",
    }


def _build_system_prompt(ctx: dict) -> str:
    cat_str = ", ".join(
        [f"{k}: ₹{v:,.0f}" for k, v in ctx['categories'].items()]
    ) if ctx['categories'] else "No category data yet."

    return f"""You are FinCoach AI — an intelligent, friendly, and highly accurate financial assistant embedded inside the Expense AI Dashboard.

## USER FINANCIAL DATA (Current Month)
- Monthly Income: ₹{ctx['monthly_income']:,.2f}
- Total Spent: ₹{ctx['total_spent']:,.2f}
- Savings Potential: ₹{ctx['savings_potential']:,.2f}
- Savings Goal: ₹{ctx['savings_goal']:,.2f}
- Category Breakdown: {cat_str}
- AI Report Excerpt: {ctx['ai_report_summary']}

## YOUR PERSONALITY
- Friendly like a smart fintech coach
- Simple English (student-friendly), no complex finance jargon
- Encouraging, positive, never judgmental
- Use short clear explanations
- Use emojis minimally and smartly (1-2 per message max)

## BEHAVIOR RULES
- ALWAYS base answers on the financial data above
- NEVER say "I don't have data" — instead say "Based on your current spending pattern..."
- If user asks savings → give optimized suggestion from their data
- If user asks "where I spend more" → compare categories from the data
- If user asks investment → give beginner-safe advice (SIP, FD, gold)
- If user asks unrealistic goal → gently correct with math
- If user asks unrelated topic → politely redirect to finance

## RESPONSE FORMAT
1. Direct answer (1-2 lines)
2. Insight from report data
3. Smart suggestion
4. Short motivational closing (optional)

Keep responses SHORT (under 120 words). No long paragraphs. Use bullet points where helpful."""


@bp.route('/api/fincoach/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()
    chat_history = data.get('history', [])  # [{role, content}, ...]

    if not user_message:
        return jsonify({'error': 'Empty message'}), 400

    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return jsonify({
            'reply': "⚠️ AI is temporarily unavailable. Please check back soon!"
        })

    ctx = _get_financial_context(session['user_id'])
    if not ctx:
        return jsonify({'reply': "Could not load your financial data. Please try again."})

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # Build Gemini chat history
        history_for_gemini = []
        for msg in chat_history[-8:]:  # Keep last 8 turns for context
            role = 'user' if msg.get('role') == 'user' else 'model'
            history_for_gemini.append({
                'role': role,
                'parts': [msg.get('content', '')]
            })

        system_prompt = _build_system_prompt(ctx)

        # Inject system prompt as first user/model turn if history is empty
        if not history_for_gemini:
            history_for_gemini = [
                {'role': 'user', 'parts': [system_prompt + "\n\nSay hi briefly and ask how you can help with my finances."]},
                {'role': 'model', 'parts': [f"Hi {ctx['user_name']}! 👋 I'm FinCoach AI, your personal finance buddy. I can see your spending data for this month. How can I help you today? 💰"]}
            ]

        chat_session = model.start_chat(history=history_for_gemini)
        
        # Add system context to each new message to keep AI grounded
        full_message = f"[CONTEXT REMINDER - do not repeat this in reply]\n{system_prompt}\n---\nUser question: {user_message}"
        response = chat_session.send_message(full_message)
        reply = response.text.strip()

        return jsonify({'reply': reply, 'ctx': {
            'income': ctx['monthly_income'],
            'spent': ctx['total_spent'],
            'savings': ctx['savings_potential'],
        }})

    except Exception as e:
        return jsonify({'reply': f"I ran into a small issue processing that. Based on your current spending pattern of ₹{ctx['total_spent']:,.0f} this month, you're doing well! Try rephrasing your question. 😊"}), 200
