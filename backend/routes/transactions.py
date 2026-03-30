from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from ..extensions import db
from ..models import Expense, User
from ..utils import runMonthlyEvaluation, CATS, detect_anomalies, categorize_with_ai, generate_spending_insights
from sqlalchemy import func
from werkzeug.utils import secure_filename
import os
import pdfplumber
import re
import hashlib
from datetime import datetime, timedelta

bp = Blueprint('transactions', __name__)

@bp.route('/add', methods=['POST'])
def add_expense():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    title = request.form.get('title')
    amount = float(request.form.get('amount'))
    category = request.form.get('category')
    include_in_total = 'include_total' in request.form
    force_submit = request.form.get('force_submit', 'false') == 'true'

    # Budget Checking Logic
    from ..models import CategoryBudget
    from sqlalchemy import extract
    if amount > 0 and not force_submit:
        budget = CategoryBudget.query.filter_by(user_id=session['user_id'], category=category).first()
        if budget and budget.monthly_limit > 0:
            now = datetime.utcnow()
            current_total = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == session['user_id'],
                Expense.category == category,
                Expense.type == 'Paid',
                extract('year', Expense.expense_date) == now.year,
                extract('month', Expense.expense_date) == now.month
            ).scalar() or 0
            
            if float(current_total) + amount > float(budget.monthly_limit):
                # Trigger Gemini
                try:
                    import google.generativeai as genai
                    model = genai.GenerativeModel('gemini-1.5-flash-latest')
                    prompt = f"System: You are 'Expense AI', a strict financial coach. User tried to spend ₹{amount} on '{category}'. Their limit is ₹{budget.monthly_limit}, but they already spent ₹{current_total}. Give a punchy 1-2 sentence warning explaining the impact and ask if they really need this. No markdown."
                    response = model.generate_content(prompt)
                    warning_msg = response.text.strip()
                except Exception as e:
                    warning_msg = f"Adding this expense exceeds your monthly {category} budget of ₹{budget.monthly_limit}. Do you want to proceed?"
                    
                if request.headers.get('Accept') == 'application/json' or request.is_json:
                    return {'status': 'budget_exceeded', 'message': warning_msg, 'category': category}, 403

    new_exp = Expense(user_id=session['user_id'], title=title, amount=abs(amount), 
                      category=category, type="Paid" if amount > 0 else "Received",
                      include_in_total=include_in_total)
    db.session.add(new_exp); db.session.commit()
    runMonthlyEvaluation(session['user_id'])
    
    # AI PRODUCTION MODULES (Production Real-time Async)
    detect_anomalies(session['user_id'], new_exp.id)
    categorize_with_ai(new_exp.id)
    now = datetime.utcnow()
    generate_spending_insights(session['user_id'], now.year, now.month)

    flash('Expense Added!', 'success')
    if request.headers.get('Accept') == 'application/json' or request.is_json:
        return {'status': 'success'}
    return redirect(url_for('transactions.manual'))

@bp.route('/delete/<id>')
def delete_expense(id):
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    exp = Expense.query.get_or_404(id)
    # Ensure ID comparison works (UUID str vs UUID obj usually handled by SA, 
    # but strictly casting user_id to string for safety if exp.user_id is UUID obj)
    if str(exp.user_id) == str(session['user_id']):
        db.session.delete(exp); db.session.commit()
        runMonthlyEvaluation(session['user_id'])
        flash('Deleted successfully.', 'info')
    return redirect(request.referrer or '/')

import google.generativeai as genai
import json

def _archive_parsed_transactions(u_id, new_filename, db_session):
    from ..models import StatementArchive, ArchiveTransaction, ActiveParserTransaction

    # 1. Fetch all currently active parsed expenses for this user
    existing_parsed = ActiveParserTransaction.query.filter_by(user_id=u_id).all()
    archived_count = len(existing_parsed)

    # Detect statement month/year from first transaction (if available)
    stmt_month = datetime.utcnow().month
    stmt_year = datetime.utcnow().year
    if existing_parsed and existing_parsed[0].date:
        stmt_month = existing_parsed[0].date.month
        stmt_year = existing_parsed[0].date.year

    # 2. Create archive record
    archive = StatementArchive(
        user_id=u_id,
        statement_month=stmt_month,
        statement_year=stmt_year,
        original_file_name=new_filename,
        total_transactions=archived_count
    )
    db_session.add(archive)
    db_session.flush()

    # 3. Move rows to archive_transactions
    for p in existing_parsed:
        arc_tx = ArchiveTransaction(
            archive_id=archive.archive_id,
            user_id=u_id,
            date=p.date,
            description=p.description,
            amount=p.amount,
            type=p.type,
            category=p.category
        )
        db_session.add(arc_tx)

    # 4. Hard-delete active parsed expenses (clean slate)
    for p in existing_parsed:
        db_session.delete(p)

    return archive, archived_count


@bp.route('/parser', methods=['GET', 'POST'])
def parser():
    from ..models import ActiveParserTransaction

    if 'user_id' not in session: return redirect(url_for('auth.login'))
    u_id = session['user_id']

    if request.method == 'POST':
        file = request.files.get('statement')
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            
            # Save file in /statements/user_id/year/month
            now = datetime.utcnow()
            user_statement_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'statements', str(u_id), str(now.year), str(now.month))
            os.makedirs(user_statement_dir, exist_ok=True)
            fpath = os.path.join(user_statement_dir, filename)
            file.save(fpath)

            try:
                # ── PHASE 1: DUPLICATE CHECK ─────────────────────────────────
                from ..models import StatementArchive
                if StatementArchive.query.filter_by(user_id=u_id, original_file_name=filename).first() or \
                   ActiveParserTransaction.query.filter_by(user_id=u_id, upload_batch=filename).first():
                    flash(f'Warning: Statement "{filename}" already exists.', 'warning')
                    return redirect(url_for('transactions.parser'))

                # ── PHASE 2: ARCHIVE & CLEAR ─────────────────────────────────
                existing_parsed = ActiveParserTransaction.query.filter_by(user_id=u_id).count()
                archived_count = 0
                if existing_parsed > 0:
                    _, archived_count = _archive_parsed_transactions(u_id, filename, db.session)

                # ── PHASE 3: EXTRACT TEXT FROM PDF ───────────────────────────
                with pdfplumber.open(fpath) as pdf:
                    text = "".join([page.extract_text() or "" for page in pdf.pages])

                # ── PHASE 4: AI PARSING ───────────────────────────────────────
                api_key = os.getenv('GOOGLE_API_KEY')
                if not api_key:
                    db.session.rollback()
                    flash('Server Error: GOOGLE_API_KEY missing.', 'danger')
                    return redirect(url_for('transactions.parser'))

                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-flash-latest')

                prompt = f"""
                You are a financial data extraction AI. Analyze the following bank statement text and extract all transactions.

                Rules:
                1. Return ONLY raw JSON array. No markdown formatting.
                2. Structure: [{{"date": "YYYY-MM-DD", "description": "Merchant/Details", "amount": 10.50, "category": "CategoryName", "type": "Paid" or "Received"}}]
                3. "Paid" = Debits/Withdrawals, "Received" = Credits/Deposits.
                4. Ignore non-transaction lines (headers, balances).
                5. Guess the category (Food, Travel, Bills, Shopping, Salary, Investment, Others).

                Text Data:
                {text[:30000]}
                """

                response = model.generate_content(prompt)
                content = response.text.strip()
                if content.startswith('```json'): content = content[7:]
                if content.startswith('```'): content = content[3:]
                if content.endswith('```'): content = content[:-3]
                
                transactions = json.loads(content.strip())

                # ── PHASE 5: INSERT NEW TRANSACTIONS ─────────────────────────
                seen_hashes = set()
                count = 0

                for t in transactions:
                    if not t.get('amount'): continue

                    amt = float(t['amount'])
                    raw_date = t.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
                    desc = t.get('description', 'Unknown')
                    tran_type = t.get('type', 'Paid')

                    hash_str = f"{u_id}-{raw_date}-{desc}-{abs(amt)}-{tran_type}"
                    t_hash = hashlib.sha256(hash_str.encode()).hexdigest()

                    if t_hash in seen_hashes: continue
                    seen_hashes.add(t_hash)

                    try: parsed_date = datetime.strptime(raw_date, '%Y-%m-%d')
                    except (ValueError, TypeError): parsed_date = datetime.utcnow()

                    new_e = ActiveParserTransaction(
                        user_id=u_id,
                        date=parsed_date,
                        description=desc[:255],
                        amount=abs(amt),
                        type=tran_type,
                        category=t.get('category', 'Others'),
                        upload_batch=filename,
                        transaction_hash=t_hash
                    )
                    db.session.add(new_e)
                    count += 1

                # ── PHASE 6: FINALISE & COMMIT ────────────────────
                db.session.commit()

                # Post-commit async tasks
                runMonthlyEvaluation(u_id)
                now = datetime.utcnow()
                generate_spending_insights(u_id, now.year, now.month)

                flash(
                    f'✅ Statement uploaded! '
                    f'{archived_count} old transactions archived. '
                    f'{count} new transactions loaded from "{filename}".',
                    'success'
                )

            except Exception as e:
                db.session.rollback()
                flash(f'AI Parsing Failed: {str(e)}', 'danger')

            return redirect(url_for('transactions.parser'))

    # GET: show only the LATEST active parser transactions
    expenses = ActiveParserTransaction.query.filter_by(user_id=u_id).order_by(ActiveParserTransaction.date.desc()).all()
    p_paid = db.session.query(func.sum(ActiveParserTransaction.amount)).filter_by(user_id=u_id, type='Paid').scalar() or 0
    p_received = db.session.query(func.sum(ActiveParserTransaction.amount)).filter_by(user_id=u_id, type='Received').scalar() or 0
    
    return render_template(
        'parser.html',
        expenses=expenses,
        p_paid=p_paid,
        p_received=p_received
    )

@bp.route('/parser/delete_active/<id>')
def delete_active_parser_transaction(id):
    from ..models import ActiveParserTransaction
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    
    tx = ActiveParserTransaction.query.get_or_404(id)
    if str(tx.user_id) == str(session['user_id']):
        db.session.delete(tx)
        db.session.commit()
        runMonthlyEvaluation(session['user_id'])
        flash('Transaction removed from current statement.', 'info')
    return redirect(url_for('transactions.parser'))

@bp.route('/api/statement/history', methods=['GET'])
def statement_history():
    from ..models import StatementArchive, ArchiveTransaction
    if 'user_id' not in session: return {'error': 'Unauthorized'}, 401
    
    u_id = session['user_id']
    archives = StatementArchive.query.filter_by(user_id=u_id).order_by(StatementArchive.archived_at.desc()).all()
    
    result = []
    for arc in archives:
        txns = ArchiveTransaction.query.filter_by(archive_id=arc.archive_id).order_by(ArchiveTransaction.date.desc()).all()
        result.append({
            'archive_id': str(arc.archive_id),
            'filename': arc.original_file_name,
            'statement_month': arc.statement_month,
            'statement_year': arc.statement_year,
            'total_transactions': arc.total_transactions,
            'archived_at': arc.archived_at.isoformat() if arc.archived_at else None,
            'transactions': [
                {
                    'id': str(t.id),
                    'date': t.date.strftime('%Y-%m-%d') if t.date else None,
                    'description': t.description,
                    'amount': float(t.amount),
                    'type': t.type,
                    'category': t.category
                } for t in txns
            ]
        })
        
    return {'history': result, 'total_uploads': len(result)}



@bp.route('/receipts', methods=['GET', 'POST'])
def receipts():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    u_id = session['user_id']
    if request.method == 'POST':
        title = request.form.get('title')
        amount = float(request.form.get('amount') or 0)
        category = request.form.get('category', 'Others')
        file = request.files.get('file')
        
        filename = None
        if file:
            filename = secure_filename(file.filename)
            fpath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(fpath)
            
        new_e = Expense(user_id=u_id, title=title, amount=amount, 
                        category=category, attachment_url=filename)
        db.session.add(new_e); db.session.commit()
        runMonthlyEvaluation(u_id)
        flash('Receipt saved to Vault!', 'success')
        return redirect(url_for('transactions.receipts'))
            
    images = Expense.query.filter(Expense.user_id == u_id, Expense.attachment_url != None).all()
    # Map 'attachment_url' to 'attachment' for template compatibility if model changed or just use attachment_url
    for img in images:
        img.attachment = img.attachment_url # Shim for template
        
    return render_template('receipts.html', images=images, cats=CATS)

@bp.route('/api/receipt/analyze', methods=['POST'])
def analyze_receipt():
    if 'user_id' not in session: return {"error": "Unauthorized"}, 401
    
    file = request.files.get('file')
    if not file: return {"error": "No file uploaded"}, 400
    
    filename = secure_filename(file.filename)
    fpath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(fpath)
    
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key: return {"error": "AI Config Missing"}, 500

    try:
        genai.configure(api_key=api_key)
        
        # This model name appeared in your list_models() output
        model_name = 'gemini-flash-latest'
        model = genai.GenerativeModel(model_name)
        
        with open(fpath, "rb") as f:
            image_data = f.read()
            
        mime_type = "image/jpeg"
        if filename.lower().endswith('.pdf'): mime_type = "application/pdf"
        elif filename.lower().endswith('.png'): mime_type = "image/png"

        prompt = """
        You are a receipt analysis engine.
        Extract structured financial data from this receipt.
        Return ONLY valid JSON.

        {
          "merchant": "string",
          "total_amount": number,
          "currency": "string",
          "date": "YYYY-MM-DD",
          "category": "Food/Travel/Shopping/Bills/Health/others",
          "confidence_score": number
        }
        No extra text allowed.
        """
        
        try:
            response = model.generate_content([prompt, {'mime_type': mime_type, 'data': image_data}])
            content = response.text.strip()
            if content.startswith('```json'): content = content[7:-3]
            if content.endswith('```'): content = content[:-3]
            
            data = json.loads(content)
            return {
                "success": True,
                "data": data,
                "filename": filename
            }
        except genai.types.BlockedPromptException as e:
            with open("ai_error_log.txt", "a") as log:
                log.write(f"[{datetime.utcnow()}] AI BLOCKED PROMPT ERROR: {str(e)}\n")
            return {"success": False, "error": "AI blocked the prompt due to safety concerns."}, 400
        except Exception as e:
            with open("ai_error_log.txt", "a") as log:
                log.write(f"[{datetime.utcnow()}] AI EXTRACTION ERROR: {str(e)}\n")
            # Check for rate limit error (429) specifically
            if "429" in str(e):
                return {"success": False, "error": "AI service is busy. Please try again later."}, 429
            return {"success": False, "error": "AI processing failed. Please try again later."}, 500
    except Exception as e:
        with open("ai_error_log.txt", "a") as f:
            f.write(f"[{datetime.utcnow()}] AI ERROR: {str(e)}\n")
        print(f"AI ERROR: {e}")
        return {"success": False, "error": str(e)}, 500

@bp.route('/manual')
def manual():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    u_id = session['user_id']
    expenses = Expense.query.filter_by(user_id=u_id, is_parsed=False, attachment_url=None).order_by(Expense.expense_date.desc()).all()
    m_paid = db.session.query(func.sum(Expense.amount)).filter_by(user_id=u_id, is_parsed=False, type='Paid').scalar() or 0
    m_received = db.session.query(func.sum(Expense.amount)).filter_by(user_id=u_id, is_parsed=False, type='Received').scalar() or 0
    cat_sum = db.session.query(Expense.category, func.sum(Expense.amount)).filter_by(user_id=u_id, is_parsed=False, type='Paid').group_by(Expense.category).all()
    
    daily_labels, daily_values = [], []
    for i in range(6, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).date()
        amt = db.session.query(func.sum(Expense.amount)).filter_by(user_id=u_id, is_parsed=False, type='Paid').filter(func.date(Expense.expense_date) == d).scalar() or 0
        daily_labels.append(d.strftime('%b %d')); daily_values.append(amt)
    in_group = False
    
    return render_template('manual.html', expenses=expenses, cats=CATS, pie_labels=[r[0] for r in cat_sum], pie_values=[r[1] for r in cat_sum], daily_labels=daily_labels, daily_values=daily_values, m_paid=m_paid, m_received=m_received, sel_cat='All', in_group=in_group)

import pandas as pd
import io
from flask import send_file

@bp.route('/api/export/csv')
def export_csv():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    u_id = session['user_id']
    expenses = Expense.query.filter_by(user_id=u_id).order_by(Expense.expense_date.desc()).all()
    
    data = []
    for e in expenses:
        data.append({
            "Date": e.expense_date.strftime('%Y-%m-%d %H:%M:%S') if e.expense_date else '',
            "Title": e.title,
            "Amount": float(e.amount),
            "Type": e.type,
            "Category": e.category
        })
        
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='ExpenseAI_Report.csv')

@bp.route('/api/export/pdf')
def export_pdf():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    u_id = session['user_id']
    
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        return "ReportLab not installed", 500

    expenses = Expense.query.filter_by(user_id=u_id).order_by(Expense.expense_date.desc()).all()

    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "ExpenseAI - Financial Report")
    
    c.setFont("Helvetica", 10)
    y = height - 80
    c.drawString(50, y, "Date")
    c.drawString(150, y, "Title")
    c.drawString(350, y, "Category")
    c.drawString(450, y, "Amount")
    c.drawString(520, y, "Type")
    
    y -= 10
    c.line(50, y, width - 50, y)
    y -= 15
    
    total_paid = 0
    total_received = 0
    
    for e in expenses:
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 50
            
        c.drawString(50, y, e.expense_date.strftime('%Y-%m-%d') if e.expense_date else '')
        title = e.title[:25] + '...' if len(e.title) > 25 else e.title
        c.drawString(150, y, title)
        c.drawString(350, y, e.category)
        c.drawString(450, y, f"Rs.{float(e.amount):.2f}")
        c.drawString(520, y, e.type)
        y -= 15
        
        if e.type == 'Paid': total_paid += e.amount
        elif e.type == 'Received': total_received += e.amount

    y -= 10
    c.line(50, y, width - 50, y)
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Total Paid: Rs.{float(total_paid):.2f}")
    c.drawString(250, y, f"Total Received: Rs.{float(total_received):.2f}")

    c.save()
    output.seek(0)
    return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='ExpenseAI_Report.pdf')
