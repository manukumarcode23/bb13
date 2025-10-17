from sqlalchemy import String, BigInteger, DateTime, Text, Boolean, Integer, Date, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from bot.database import Base
from datetime import datetime, date
from typing import Optional

class File(Base):
    """Model for storing file information"""
    __tablename__ = "files"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(BigInteger)
    mime_type: Mapped[str] = mapped_column(String(100))
    access_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    video_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    temporary_stream_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    temporary_download_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    link_expiry_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_by_android_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    publisher_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class User(Base):
    """Model for storing user information"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=False)

class AccessLog(Base):
    """Model for logging file access"""
    __tablename__ = "access_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_ip: Mapped[str] = mapped_column(String(45))  # IPv6 support
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)
    access_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    success: Mapped[bool] = mapped_column(Boolean, default=True)

class LinkTransaction(Base):
    """Model for tracking link delivery to external API"""
    __tablename__ = "link_transactions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(BigInteger, index=True)
    android_id: Mapped[str] = mapped_column(String(100), index=True)
    hash_id: Mapped[str] = mapped_column(String(32), index=True)
    stream_link: Mapped[str] = mapped_column(Text)
    download_link: Mapped[str] = mapped_column(Text)
    callback_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    callback_method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    callback_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    callback_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)

class Publisher(Base):
    """Model for storing publisher information"""
    __tablename__ = "publishers"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    traffic_source: Mapped[str] = mapped_column(Text)
    api_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, unique=True, index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class AdMobSettings(Base):
    """Model for storing AdMob ads settings"""
    __tablename__ = "admob_settings"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    rewarded_ad_unit: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rewarded_api_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    banner_ad_unit: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    banner_api_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    interstitial_ad_unit: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    interstitial_api_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AdNetwork(Base):
    """Model for storing multiple ad network configurations"""
    __tablename__ = "ad_networks"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    network_name: Mapped[str] = mapped_column(String(100), index=True)
    banner_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    interstitial_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rewarded_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    banner_daily_limit: Mapped[int] = mapped_column(Integer, default=0)
    interstitial_daily_limit: Mapped[int] = mapped_column(Integer, default=0)
    rewarded_daily_limit: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default='active')
    priority: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AdPlayCount(Base):
    """Model for tracking daily ad play counts per user"""
    __tablename__ = "ad_play_counts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_network_id: Mapped[int] = mapped_column(Integer, index=True)
    ad_type: Mapped[str] = mapped_column(String(20), index=True)
    android_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    user_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True, index=True)
    play_date: Mapped[date] = mapped_column(Date, index=True, server_default=func.current_date())
    play_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PublisherImpression(Base):
    """Model for tracking publisher video impressions"""
    __tablename__ = "publisher_impressions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    publisher_id: Mapped[int] = mapped_column(Integer, index=True)
    hash_id: Mapped[str] = mapped_column(String(32), index=True)
    android_id: Mapped[str] = mapped_column(String(255), index=True)
    user_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    impression_date: Mapped[date] = mapped_column(Date, index=True, server_default=func.current_date())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Settings(Base):
    """Model for storing application settings"""
    __tablename__ = "settings"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    terms_of_service: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    privacy_policy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    impression_rate: Mapped[float] = mapped_column(Float, default=0.0)
    android_package_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    android_deep_link_scheme: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    minimum_withdrawal: Mapped[float] = mapped_column(Float, default=10.0)
    ads_api_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    callback_mode: Mapped[str] = mapped_column(String(10), default='POST')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class BankAccount(Base):
    """Model for storing publisher bank account information"""
    __tablename__ = "bank_accounts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    publisher_id: Mapped[int] = mapped_column(Integer, index=True)
    account_holder_name: Mapped[str] = mapped_column(String(255))
    bank_name: Mapped[str] = mapped_column(String(255))
    account_number: Mapped[str] = mapped_column(String(100))
    routing_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    swift_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    country: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class WithdrawalRequest(Base):
    """Model for tracking publisher withdrawal requests"""
    __tablename__ = "withdrawal_requests"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    publisher_id: Mapped[int] = mapped_column(Integer, index=True)
    bank_account_id: Mapped[int] = mapped_column(Integer, index=True)
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)