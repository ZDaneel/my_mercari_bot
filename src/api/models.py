"""
API数据模型
定义FastAPI后端使用的Pydantic模型
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class MonitorConfig(BaseModel):
    """监控配置模型"""
    keywords: List[str] = Field(..., description="监控关键词列表")
    min_interval: int = Field(60, ge=10, le=3600, description="最小监控间隔(秒)")
    max_interval: int = Field(90, ge=10, le=3600, description="最大监控间隔(秒)")
    page_size: int = Field(20, ge=1, le=100, description="每页商品数量")
    link_type: str = Field("mercari", description="链接类型: mercari/letaoyifan")
    notifier_type: str = Field("console", description="通知类型: console/windows")

class ItemInfo(BaseModel):
    """商品信息模型"""
    id: str
    title: str
    price: int
    image_url: Optional[str] = None
    link: str
    created_at: datetime
    keyword: str

class MonitorStatus(BaseModel):
    """监控状态模型"""
    task_id: str
    status: str  # running, stopped, error
    keywords: List[str]
    last_check: Optional[datetime] = None
    items_found: int = 0
    error_message: Optional[str] = None

class SearchRequest(BaseModel):
    """搜索请求模型"""
    keywords: List[str] = Field(..., description="搜索关键词")
    limit: int = Field(20, ge=1, le=100, description="返回结果数量限制")

class SearchResponse(BaseModel):
    """搜索响应模型"""
    items: List[ItemInfo]
    total: int
    keywords: List[str]
    search_time: datetime
