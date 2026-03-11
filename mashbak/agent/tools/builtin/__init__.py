"""Built-in tools initialization"""
from .dir_inbox import DirInboxTool
from .dir_outbox import DirOutboxTool
from .list_files import ListFilesTool
from .system_info import SystemInfoTool
from .cpu_usage import CpuUsageTool
from .disk_space import DiskSpaceTool
from .current_time import CurrentTimeTool
from .network_status import NetworkStatusTool
from .list_processes import ListProcessesTool
from .uptime import UptimeTool
from .email_tools import ListRecentEmailsTool, SummarizeInboxTool, SearchEmailsTool, ReadEmailThreadTool
from .config_tools import SetConfigVariableTool

ALL_BUILTIN_TOOLS = [
    DirInboxTool(),
    DirOutboxTool(),
    ListFilesTool(),
    SystemInfoTool(),
    CpuUsageTool(),
    DiskSpaceTool(),
    CurrentTimeTool(),
    NetworkStatusTool(),
    ListProcessesTool(),
    UptimeTool(),
    ListRecentEmailsTool(),
    SummarizeInboxTool(),
    SearchEmailsTool(),
    ReadEmailThreadTool(),
    SetConfigVariableTool(),
]

__all__ = ["ALL_BUILTIN_TOOLS"]
