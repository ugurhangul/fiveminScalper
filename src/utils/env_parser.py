"""
Environment Variable Parser Utility

Centralizes environment variable parsing logic with type conversion and validation.
Eliminates code duplication in config.py and provides consistent error handling.
"""
import os
from typing import Optional, Union


class EnvParser:
    """Utility class for parsing environment variables with type conversion"""
    
    @staticmethod
    def get_bool(var_name: str, default: bool = False) -> bool:
        """
        Parse boolean environment variable.
        
        Args:
            var_name: Environment variable name
            default: Default value if not set
            
        Returns:
            Boolean value
        """
        value = os.getenv(var_name, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    @staticmethod
    def get_int(var_name: str, default: int = 0) -> int:
        """
        Parse integer environment variable.
        
        Args:
            var_name: Environment variable name
            default: Default value if not set
            
        Returns:
            Integer value
        """
        try:
            return int(os.getenv(var_name, str(default)))
        except ValueError:
            return default
    
    @staticmethod
    def get_float(var_name: str, default: float = 0.0) -> float:
        """
        Parse float environment variable.
        
        Args:
            var_name: Environment variable name
            default: Default value if not set
            
        Returns:
            Float value
        """
        try:
            return float(os.getenv(var_name, str(default)))
        except ValueError:
            return default
    
    @staticmethod
    def get_string(var_name: str, default: str = '') -> str:
        """
        Parse string environment variable.
        
        Args:
            var_name: Environment variable name
            default: Default value if not set
            
        Returns:
            String value
        """
        return os.getenv(var_name, default)
    
    @staticmethod
    def get_lot_size(var_name: str, default: Union[float, str] = 0.01) -> float:
        """
        Parse lot size environment variable with special handling for "MIN".
        
        Args:
            var_name: Environment variable name
            default: Default value if not set (can be float or "MIN")
            
        Returns:
            Float value (0.0 if "MIN" to signal using symbol's minimum)
        """
        value_str = os.getenv(var_name, str(default)).strip().upper()
        if value_str == 'MIN':
            return 0.0
        try:
            return float(value_str)
        except ValueError:
            # If conversion fails, return 0.0 (use symbol minimum)
            return 0.0
    
    @staticmethod
    def get_optional_string(var_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Parse optional string environment variable.
        
        Args:
            var_name: Environment variable name
            default: Default value if not set
            
        Returns:
            String value or None
        """
        value = os.getenv(var_name)
        if value is None or value.strip() == '':
            return default
        return value
    
    @staticmethod
    def get_list(var_name: str, separator: str = ',', default: Optional[list] = None) -> list:
        """
        Parse list environment variable (comma-separated by default).
        
        Args:
            var_name: Environment variable name
            separator: Separator character (default: comma)
            default: Default value if not set
            
        Returns:
            List of strings
        """
        value = os.getenv(var_name)
        if value is None or value.strip() == '':
            return default or []
        return [item.strip() for item in value.split(separator) if item.strip()]
    
    @staticmethod
    def validate_required(var_name: str) -> str:
        """
        Validate that a required environment variable is set.
        
        Args:
            var_name: Environment variable name
            
        Returns:
            String value
            
        Raises:
            ValueError: If variable is not set or empty
        """
        value = os.getenv(var_name)
        if value is None or value.strip() == '':
            raise ValueError(f"Required environment variable '{var_name}' is not set")
        return value
    
    @staticmethod
    def get_int_range(var_name: str, default: int, min_value: Optional[int] = None, 
                      max_value: Optional[int] = None) -> int:
        """
        Parse integer environment variable with range validation.
        
        Args:
            var_name: Environment variable name
            default: Default value if not set
            min_value: Minimum allowed value (optional)
            max_value: Maximum allowed value (optional)
            
        Returns:
            Integer value clamped to range
        """
        value = EnvParser.get_int(var_name, default)
        
        if min_value is not None:
            value = max(value, min_value)
        if max_value is not None:
            value = min(value, max_value)
            
        return value
    
    @staticmethod
    def get_float_range(var_name: str, default: float, min_value: Optional[float] = None,
                        max_value: Optional[float] = None) -> float:
        """
        Parse float environment variable with range validation.
        
        Args:
            var_name: Environment variable name
            default: Default value if not set
            min_value: Minimum allowed value (optional)
            max_value: Maximum allowed value (optional)
            
        Returns:
            Float value clamped to range
        """
        value = EnvParser.get_float(var_name, default)
        
        if min_value is not None:
            value = max(value, min_value)
        if max_value is not None:
            value = min(value, max_value)
            
        return value

