__all__ = (
    "FSError",
    "FileExists",
    "FileNotFound",
    "UnauthorizedFileType",
    "UploadNotAllowed",
    "OperationNotSupported",
)


class FSError(Exception):
    """Base class for all Flask-FS Exceptions"""


class UnauthorizedFileType(FSError):
    """This exception is raised when trying to upload an unauthorized file type."""


class UploadNotAllowed(FSError):
    """Raised when trying to upload into storage where upload is not allowed."""


class FileExists(FSError):
    """Raised when trying to overwrite an existing file"""


class FileNotFound(FSError):
    """Raised when trying to access a non existant file"""


class OperationNotSupported(FSError):
    """Raised when trying to perform an operation not supported by the current backend"""
