# blackduck_server.py
from fastmcp import FastMCP
from blackduck import Client
from typing import Optional, List
from pydantic import BaseModel
import logging
from datetime import datetime
import os
from config.config import *

# 创建日志目录
os.makedirs(LOG_DIR, exist_ok=True)

# 配置日志
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f'blackduck_mcp_{datetime.now().strftime("%Y%m%d")}.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('blackduck_mcp')

class ProjectInfo(BaseModel):
    """项目信息数据模型"""
    name: str
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class BlackDuckMCP:
    """BlackDuck MCP服务类"""
    def __init__(self, base_url: str, api_token: str):
        self.client = Client(
            token=api_token,
            base_url=base_url
        )
        logger.info(f"BlackDuck client initialized with base_url: {base_url}")

# 创建MCP服务器实例
mcp = FastMCP("BlackDuck Service")
bd_service = None

@mcp.on_startup
async def startup():
    """服务启动初始化"""
    global bd_service
    try:
        bd_service = BlackDuckMCP(
            base_url=BLACKDUCK_URL,
            api_token=BLACKDUCK_TOKEN
        )
        logger.info("MCP server started and BlackDuck service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize BlackDuck service: {str(e)}")
        raise

@mcp.tool()
async def unlock_user(user_id: str) -> dict:
    """
    解锁BlackDuck用户
    
    Args:
        user_id: 要解锁的用户ID
    
    Returns:
        dict: 操作结果
    """
    logger.info(f"Attempting to unlock user: {user_id}")
    try:
        response = bd_service.client.put(f'/api/users/{user_id}/unlock')
        logger.info(f"Successfully unlocked user: {user_id}")
        return {
            "status": "success",
            "message": f"User {user_id} unlocked successfully"
        }
    except Exception as e:
        error_msg = f"Failed to unlock user {user_id}: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg
        }

@mcp.tool()
async def get_projects(
    name: Optional[str] = None,
    description: Optional[str] = None
) -> List[ProjectInfo]:
    """
    获取BlackDuck项目信息
    
    Args:
        name: 项目名称过滤
        description: 项目描述过滤
    
    Returns:
        List[ProjectInfo]: 项目信息列表
    """
    logger.info(f"Fetching projects with filters - name: {name}, description: {description}")
    try:
        projects = []
        for project in bd_service.client.get_resource('projects'):
            if name and name.lower() not in project['name'].lower():
                continue
            if description and description.lower() not in project.get('description', '').lower():
                continue
            
            projects.append(ProjectInfo(
                name=project['name'],
                description=project.get('description'),
                created_at=project.get('createdAt'),
                updated_at=project.get('updatedAt')
            ))
        
        logger.info(f"Successfully retrieved {len(projects)} projects")
        return projects
    except Exception as e:
        error_msg = f"Failed to fetch projects: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg
        }

@mcp.on_shutdown
async def shutdown():
    """服务关闭清理"""
    logger.info("MCP server shutting down")

if __name__ == "__main__":
    mcp.run()
