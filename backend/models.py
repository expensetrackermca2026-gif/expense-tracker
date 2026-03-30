import uuid
from datetime import datetime
from .extensions import db
from sqlalchemy import func, text, JSON, String
import enum

# --- ENUMS ---
class UserRole(enum.Enum):
    USER = 'user'
    ADMIN = 'admin'
    MODERATOR = 'moderator'

class AuthProviderType(enum.Enum):
    EMAIL = 'email'
    GOOGLE = 'google'
    GITHUB = 'github'
    APPLE = 'apple'

class ChatSender(enum.Enum):
    USER = 'user'
    AI = 'ai'
    SYSTEM = 'system'

class EventSeverity(enum.Enum):
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'

# --- CORE IDENTITY TABLES ---

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(100))
    avatar_url = db.Column(db.Text)
    role = db.Column(db.Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    project_settings = db.Column(JSON, default={})
    monthly_income = db.Column(db.Numeric(15, 2), default=0.00)
    savings_goal = db.Column(db.Numeric(15, 2), default=0.00)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    auth_providers = db.relationship('UserAuthProvider', backref='user', lazy=True, cascade="all, delete-orphan")
    sessions = db.relationship('Session', backref='user', lazy=True, cascade="all, delete-orphan")
    refresh_tokens = db.relationship('RefreshToken', backref='user', lazy=True, cascade="all, delete-orphan")
    expenses = db.relationship('Expense', backref='owner', lazy=True, cascade="all, delete-orphan")
    monthly_summaries = db.relationship('MonthlySummary', backref='user', lazy=True, cascade="all, delete-orphan")
    chat_sessions = db.relationship('ChatSession', backref='user', lazy=True, cascade="all, delete-orphan")

class UserAuthProvider(db.Model):
    __tablename__ = 'user_auth_providers'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    provider = db.Column(db.Enum(AuthProviderType), nullable=False)
    provider_user_id = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True))
    __table_args__ = (db.UniqueConstraint('provider', 'provider_user_id', name='unique_provider_user'),)

class Session(db.Model):
    __tablename__ = 'sessions'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = db.Column(db.String(255), unique=True, nullable=False, index=True)
    ip_address = db.Column(String(45))
    user_agent = db.Column(db.Text)
    is_valid = db.Column(db.Boolean, default=True, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = db.Column(db.String(255), unique=True, nullable=False)
    parent_session_id = db.Column(String(36), db.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = db.Column(db.DateTime(timezone=True))

class PasswordReset(db.Model):
    __tablename__ = 'password_resets'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = db.Column(db.String(255), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

class EmailVerification(db.Model):
    __tablename__ = 'email_verifications'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = db.Column(db.String(255), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    verified_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(15, 2), default=0.00, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), default="Paid")
    attachment_url = db.Column(db.Text)
    expense_date = db.Column(db.DateTime(timezone=True), default=func.now())
    is_parsed = db.Column(db.Boolean, default=False)
    statement_tag = db.Column(db.String(100))
    transaction_hash = db.Column(db.String(64), unique=True, index=True)
    include_in_total = db.Column(db.Boolean, default=True)
    ai_category_suggestion = db.Column(db.String(50))
    is_anomaly = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (db.Index('idx_expenses_user_date', 'user_id', text('expense_date DESC')),)

class CategoryBudget(db.Model):
    __tablename__ = 'category_budgets'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    monthly_limit = db.Column(db.Numeric(15, 2), default=0.00, nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'category', name='unique_user_category_budget'),)

class MonthlySummary(db.Model):
    __tablename__ = 'monthly_summaries'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    total_income = db.Column(db.Numeric(15, 2), default=0.00)
    total_expenses = db.Column(db.Numeric(15, 2), default=0.00)
    total_savings = db.Column(db.Numeric(15, 2), default=0.00)
    current_balance = db.Column(db.Numeric(15, 2), default=0.00)
    goal_status = db.Column(db.String(50), default="PENDING")
    last_updated = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'year', 'month', name='unique_monthly_summary'),)

class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255))
    metadata_ = db.Column('metadata', JSON, default={})
    is_archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade="all, delete-orphan")

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(String(36), db.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False)
    sender = db.Column(db.Enum(ChatSender), nullable=False)
    content = db.Column(db.Text, nullable=False)
    tokens_used = db.Column(db.Integer)
    metadata_ = db.Column('metadata', JSON, default={})
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (db.Index('idx_chat_messages_session', 'session_id', text('created_at ASC')),)

class LoginAuditLog(db.Model):
    __tablename__ = 'login_audit_logs'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    attempt_email = db.Column(db.String(255))
    auth_provider = db.Column(db.Enum(AuthProviderType), nullable=True)
    ip_address = db.Column(String(45))
    user_agent = db.Column(db.Text)
    status = db.Column(db.String(50), nullable=False)
    failure_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (db.Index('idx_audit_user_ip', 'user_id', 'ip_address'),)

class UserActivityHistory(db.Model):
    __tablename__ = 'user_activity_history'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    action_type = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(String(36))
    details = db.Column(JSON)
    ip_address = db.Column(String(45))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

class SystemEvent(db.Model):
    __tablename__ = 'system_events'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = db.Column(db.String(100), nullable=False)
    severity = db.Column(db.Enum(EventSeverity), default=EventSeverity.INFO)
    payload = db.Column(JSON, default={})
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (db.Index('idx_system_events_type', 'event_type', text('created_at DESC')),)

class AIReport(db.Model):
    __tablename__ = 'ai_reports'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(50))
    year = db.Column(db.Integer)
    month = db.Column(db.Integer)
    content = db.Column(db.Text)
    data_snapshot = db.Column(JSON)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

class InvestmentPlan(db.Model):
    __tablename__ = 'investment_plans'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    savings_goal = db.Column(db.Numeric(15, 2))
    plan_json = db.Column(JSON)
    advice_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

class AnomalyWarning(db.Model):
    __tablename__ = 'anomaly_warnings'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    expense_id = db.Column(String(36), db.ForeignKey('expenses.id', ondelete='CASCADE'))
    type = db.Column(db.String(50))
    reason = db.Column(db.Text)
    amount_diff = db.Column(db.Numeric(15, 2))
    percentage_spike = db.Column(db.Numeric(15, 2))
    is_resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

class SavingsRecommendation(db.Model):
    __tablename__ = 'savings_recommendations'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    monthly_income = db.Column(db.Numeric(15, 2), nullable=False)
    recommended_savings = db.Column(db.Numeric(15, 2), nullable=False)
    needs_amount = db.Column(db.Numeric(15, 2), nullable=False)
    wants_amount = db.Column(db.Numeric(15, 2), nullable=False)
    emergency_fund_goal = db.Column(db.Numeric(15, 2), nullable=False)
    months_to_reach_goal = db.Column(db.Numeric(15, 2), nullable=False)
    explanation = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

class ActiveParserTransaction(db.Model):
    __tablename__ = 'active_parser_transactions'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.DateTime(timezone=True))
    description = db.Column(db.String(255))
    amount = db.Column(db.Numeric(15, 2))
    type = db.Column(db.String(20))
    category = db.Column(db.String(100), default='Others')
    upload_batch = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    transaction_hash = db.Column(db.String(64))
    __table_args__ = (db.Index('idx_apt_user_date', 'user_id', 'date'),)

class StatementArchive(db.Model):
    __tablename__ = 'statement_archive'
    archive_id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    statement_month = db.Column(db.Integer)
    statement_year = db.Column(db.Integer)
    original_file_name = db.Column(db.String(255))
    total_transactions = db.Column(db.Integer, default=0)
    archived_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    transactions = db.relationship('ArchiveTransaction', backref='archive', cascade='all, delete-orphan')

class ArchiveTransaction(db.Model):
    __tablename__ = 'archive_transactions'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    archive_id = db.Column(String(36), db.ForeignKey('statement_archive.archive_id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.DateTime(timezone=True))
    description = db.Column(db.String(255))
    amount = db.Column(db.Numeric(15, 2))
    type = db.Column(db.String(20))
    category = db.Column(db.String(100), default='Others')

class LoginAudit(db.Model):
    __tablename__ = 'login_audits'
    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    email_attempted = db.Column(db.String(255))
    ip_address = db.Column(String(45))
    user_agent = db.Column(db.Text)
    status = db.Column(db.String(20))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
