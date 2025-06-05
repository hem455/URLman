"""
ログ設定モジュール
構造化ログ、ローテーション機能、レベル設定を提供
"""

import logging
import logging.handlers
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

class StructuredFormatter(logging.Formatter):
    """構造化ログ（JSON形式）のフォーマッター"""
    
    def format(self, record: logging.LogRecord) -> str:
        # 基本的なログ情報
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage()
        }
        
        # 例外情報がある場合は追加
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)

def get_logger(name: str) -> logging.Logger:
    """便利関数：ロガーを簡単に取得"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        # 基本的なハンドラー設定
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger 