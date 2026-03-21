from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..extensions import db
from ..models import User, Expense, FamilyGroup, FamilyMember
from sqlalchemy import func
from datetime import datetime

bp = Blueprint('family', __name__)

@bp.route('/family')
def index():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    u_id = session['user_id']
    user = User.query.get(u_id)
    
    # Find user's group
    membership = FamilyMember.query.filter_by(user_id=u_id).first()
    if not membership:
        return render_template('family/onboarding.html')
    
    group = FamilyGroup.query.get(membership.group_id)
    members = FamilyMember.query.filter_by(group_id=group.id).all()
    
    # Shared Expenses
    shared_expenses = Expense.query.filter_by(group_id=group.id).order_by(Expense.expense_date.desc()).all()
    
    # Group Stats
    group_total = db.session.query(func.sum(Expense.amount)).filter_by(group_id=group.id, type='Paid').scalar() or 0
    member_split = []
    for m in members:
        m_user = User.query.get(m.user_id)
        m_spent = db.session.query(func.sum(Expense.amount)).filter_by(group_id=group.id, user_id=m.user_id, type='Paid').scalar() or 0
        member_split.append({
            'name': m_user.full_name or m_user.email,
            'spent': m_spent
        })
        
    return render_template('family/dashboard.html', group=group, members=members, 
                           shared_expenses=shared_expenses, group_total=group_total, 
                           member_split=member_split, current_user_id=u_id)

@bp.route('/family/create', methods=['POST'])
def create():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    name = request.form.get('group_name')
    if not name:
        flash('Group name is required', 'error')
        return redirect(url_for('family.index'))
    
    u_id = session['user_id']
    new_group = FamilyGroup(name=name, created_by=u_id)
    db.session.add(new_group)
    db.session.flush() # Get ID
    
    membership = FamilyMember(group_id=new_group.id, user_id=u_id, role='ADMIN')
    db.session.add(membership)
    db.session.commit()
    
    flash(f'Family Group "{name}" created!', 'success')
    return redirect(url_for('family.index'))

@bp.route('/family/join', methods=['POST'])
def join():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    group_id_str = request.form.get('group_id')
    if not group_id_str:
        flash('Group ID required', 'error')
        return redirect(url_for('family.index'))
    
    try:
        import uuid
        g_id = uuid.UUID(group_id_str)
    except:
        flash('Invalid Group ID format', 'error')
        return redirect(url_for('family.index'))
        
    group = FamilyGroup.query.get(g_id)
    if not group:
        flash('Group not found', 'error')
        return redirect(url_for('family.index'))
        
    u_id = session['user_id']
    existing = FamilyMember.query.filter_by(user_id=u_id).first()
    if existing:
        flash('You are already in a group', 'warning')
        return redirect(url_for('family.index'))
        
    membership = FamilyMember(group_id=group.id, user_id=u_id, role='MEMBER')
    db.session.add(membership)
    db.session.commit()
    
    flash(f'Joined {group.name}!', 'success')
    return redirect(url_for('family.index'))
