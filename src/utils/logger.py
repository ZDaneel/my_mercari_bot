#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志管理模块
提供统一的日志配置和管理功能
"""

import logging
import logging.handlers
import sys
import os
from pathlib import Path
from datetime import datetime
import queue
import threading
from typing import Optional, Dict, Any

def get_project_root() -> Path:
    """
    获取项目根目录，兼容打包和非打包环境
    
    Returns:
        Path: 项目根目录路径
    """
    if getattr(sys, 'frozen', False):
        # 打包环境：exe文件所在目录
        return Path(sys.executable).parent
    else:
        # 开发环境：当前文件所在目录的上级目录
        return Path(__file__).resolve().parent.parent.parent

def get_resource_path(resource_name: str) -> Path:
    """
    获取资源文件路径，兼容打包和非打包环境
    
    Args:
        resource_name (str): 资源名称，如 "driver/chromedriver.exe"
    
    Returns:
        Path: 资源文件的完整路径
    """
    root_dir = get_project_root()
    
    if getattr(sys, 'frozen', False):
        # 打包环境：先尝试 _internal 目录，再尝试根目录
        internal_path = root_dir / "_internal" / resource_name
        if internal_path.exists():
            return internal_path
        
        # 如果 _internal 中不存在，尝试根目录
        root_path = root_dir / resource_name
        if root_path.exists():
            return root_path
        
        # 如果都不存在，返回 _internal 路径（用于错误提示）
        return internal_path
    else:
        # 开发环境：直接使用根目录
        return root_dir / resource_name

class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }
    
    def format(self, record):
        # 添加颜色
        if hasattr(record, 'levelname') and record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        
        # 添加表情符号
        emoji_map = {
            'DEBUG': '🔍',
            'INFO': 'ℹ️',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'CRITICAL': '🚨'
        }
        
        if record.levelname in emoji_map:
            record.msg = f"{emoji_map[record.levelname]} {record.msg}"
        
        return super().format(record)

class QueueHandler(logging.Handler):
    """队列处理器，用于GUI显示"""
    
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
        self.formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
    
    def emit(self, record):
        try:
            msg = self.formatter.format(record)
            self.log_queue.put(msg)
        except Exception:
            self.handleError(record)

class LogManager:
    """日志管理器"""
    
    def __init__(self, app_name: str = "MercariBot"):
        self.app_name = app_name
        self.log_queue = queue.Queue()
        self.loggers: Dict[str, logging.Logger] = {}
        self.handlers: Dict[str, logging.Handler] = {}
        
        # 获取应用根目录
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后的路径
            self.base_path = Path(sys.executable).parent
        else:
            # 开发环境路径
            self.base_path = Path(__file__).resolve().parent.parent.parent
        
        # 创建日志目录
        self.log_dir = self.base_path / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
        # 日志文件路径
        self.log_file = self.log_dir / f"{app_name.lower()}.log"
        self.error_log_file = self.log_dir / f"{app_name.lower()}_error.log"
        
        # 初始化日志配置
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志配置"""
        # 创建根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 创建处理器
        self._create_handlers()
        
        # 设置第三方库的日志级别
        self._setup_third_party_logging()
    
    def _create_handlers(self):
        """创建各种日志处理器"""
        
        # 1. 控制台处理器（彩色输出）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        
        # 2. 文件处理器（详细日志）
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # 3. 错误文件处理器
        error_handler = logging.handlers.RotatingFileHandler(
            self.error_log_file,
            maxBytes=5*1024*1024,   # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s\n'
            'Exception: %(exc_info)s\n',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_formatter)
        
        # 4. GUI队列处理器
        gui_handler = QueueHandler(self.log_queue)
        gui_handler.setLevel(logging.INFO)
        
        # 添加到根日志记录器
        root_logger = logging.getLogger()
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_handler)
        root_logger.addHandler(gui_handler)
        
        # 保存处理器引用
        self.handlers = {
            'console': console_handler,
            'file': file_handler,
            'error': error_handler,
            'gui': gui_handler
        }
    
    def _setup_third_party_logging(self):
        """设置第三方库的日志级别"""
        # 降低第三方库的日志级别
        third_party_loggers = [
            'selenium',
            'seleniumwire',
            'webdriver_manager',
            'urllib3',
            'requests',
            'PIL',
            'matplotlib',
            'numpy',
            'pandas'
        ]
        
        for logger_name in third_party_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.WARNING)
            logger.propagate = False
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志记录器"""
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)
        return self.loggers[name]
    
    def get_queue(self) -> queue.Queue:
        """获取日志队列，用于GUI显示"""
        return self.log_queue
    
    def set_level(self, level: str):
        """设置日志级别"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        
        if level.upper() in level_map:
            logging.getLogger().setLevel(level_map[level.upper()])
            logging.info(f"📊 日志级别已设置为: {level.upper()}")
    
    def log_startup(self):
        """记录启动信息"""
        logger = self.get_logger('startup')
        logger.info("🚀 应用启动")
        logger.info(f"📁 工作目录: {self.base_path}")
        logger.info(f"📝 日志目录: {self.log_dir}")
        logger.info(f"🐍 Python版本: {sys.version}")
        logger.info(f"💻 操作系统: {sys.platform}")
    
    def log_shutdown(self):
        """记录关闭信息"""
        logger = self.get_logger('shutdown')
        logger.info("🛑 应用关闭")
        
        # 刷新所有处理器
        for handler in logging.getLogger().handlers:
            handler.flush()
    
    def cleanup_old_logs(self, days: int = 30):
        """清理旧日志文件"""
        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
            count = 0
            
            for log_file in self.log_dir.glob("*.log*"):
                if log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
                    count += 1
            
            if count > 0:
                logging.info(f"🧹 清理了 {count} 个旧日志文件")
        except Exception as e:
            logging.error(f"清理日志文件失败: {e}")

# 全局日志管理器实例
_log_manager: Optional[LogManager] = None

def get_log_manager() -> LogManager:
    """获取全局日志管理器实例"""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
    return _log_manager

def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return get_log_manager().get_logger(name)

def setup_logging(app_name: str = "MercariBot") -> LogManager:
    """设置日志系统"""
    global _log_manager
    _log_manager = LogManager(app_name)
    return _log_manager

# 便捷的日志函数
def log_info(message: str, logger_name: str = "main"):
    """记录信息日志"""
    get_logger(logger_name).info(message)

def log_warning(message: str, logger_name: str = "main"):
    """记录警告日志"""
    get_logger(logger_name).warning(message)

def log_error(message: str, logger_name: str = "main", exc_info: bool = True):
    """记录错误日志"""
    get_logger(logger_name).error(message, exc_info=exc_info)

def log_debug(message: str, logger_name: str = "main"):
    """记录调试日志"""
    get_logger(logger_name).debug(message)

def log_critical(message: str, logger_name: str = "main", exc_info: bool = True):
    """记录严重错误日志"""
    get_logger(logger_name).critical(message, exc_info=exc_info)
