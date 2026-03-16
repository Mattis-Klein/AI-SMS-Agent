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
from .create_folder import CreateFolderTool
from .create_file import CreateFileTool
from .delete_file import DeleteFileTool
from .edit_file import EditFileTool
from .copy_file import CopyFileTool
from .move_file import MoveFileTool
from .search_files import SearchFilesTool
from .launch_program import LaunchProgramTool
from .open_target import OpenTargetTool
from .run_project_command import RunProjectCommandTool
from .capture_screenshot import CaptureScreenshotTool
from .generate_homepage import GenerateHomepageTool
from .email_send import SendEmailTool, DraftReplyTool
from .web_search import WebSearchTool

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
    CreateFolderTool(),
    CreateFileTool(),
    DeleteFileTool(),
    EditFileTool(),
    CopyFileTool(),
    MoveFileTool(),
    SearchFilesTool(),
    LaunchProgramTool(),
    OpenTargetTool(),
    RunProjectCommandTool(),
    CaptureScreenshotTool(),
    GenerateHomepageTool(),
    SendEmailTool(),
    DraftReplyTool(),
    WebSearchTool(),
]

__all__ = ["ALL_BUILTIN_TOOLS"]
