#!/usr/bin/env python3
"""
开发服务器启动脚本
"""

import uvicorn
from transit.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "transit.main:app", host="0.0.0.0", port=settings.write_port, reload=True, log_level="info"
    )
