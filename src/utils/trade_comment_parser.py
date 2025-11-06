"""
Trade Comment Parser Utility

Centralizes trade comment generation and parsing logic.
Provides consistent comment format across the application.
"""
from typing import Optional, Dict
from src.models.data_models import TradeSignal, PositionType
from src.constants import StrategyConstants


class TradeCommentParser:
    """Utility class for generating and parsing trade comments"""
    
    # MT5 comment length limit
    MAX_COMMENT_LENGTH = 31
    
    @staticmethod
    def generate(signal: TradeSignal) -> str:
        """
        Generate informative trade comment based on signal details.
        
        Comment format: "STRATEGY|DIRECTION|CONFIRMATIONS|RANGE"
        Examples:
            - "TB|BUY|V|4H5M" - True Breakout, BUY, Volume confirmed, 4H_5M range
            - "FB|SELL|VD|15M1M" - False Breakout, SELL, Volume+Divergence, 15M_1M range
            - "TB|BUY|NC" - True Breakout, BUY, No confirmations, default range
        
        Args:
            signal: TradeSignal object
            
        Returns:
            Formatted comment string (max 31 characters for MT5)
        """
        # Determine strategy type
        if signal.is_true_breakout:
            strategy = StrategyConstants.STRATEGY_TYPE_TRUE_BREAKOUT
        else:
            strategy = StrategyConstants.STRATEGY_TYPE_FALSE_BREAKOUT
        
        # Determine confirmations
        confirmations = []
        if signal.volume_confirmed:
            confirmations.append("V")
        if signal.divergence_confirmed:
            confirmations.append("D")
        
        conf_str = "".join(confirmations) if confirmations else "NC"
        
        # Include range ID if not default (for multi-range mode)
        range_info = ""
        if signal.range_id and signal.range_id != "default":
            # Extract meaningful range identifier (e.g., "4H_5M" -> "4H5M")
            range_info = signal.range_id.replace("_", "")
        
        # Build comment: Strategy|Direction|Confirmations|Range
        if range_info:
            comment = f"{strategy}|{signal.signal_type.value.upper()}|{conf_str}|{range_info}"
        else:
            comment = f"{strategy}|{signal.signal_type.value.upper()}|{conf_str}"
        
        # MT5 has a 31 character limit for comments
        if len(comment) > TradeCommentParser.MAX_COMMENT_LENGTH:
            comment = comment[:TradeCommentParser.MAX_COMMENT_LENGTH]
        
        return comment
    
    @staticmethod
    def parse(comment: str) -> Dict[str, str]:
        """
        Parse trade comment to extract strategy information.
        
        Args:
            comment: Trade comment string (e.g., "TB|BUY|V|4H5M")
            
        Returns:
            Dictionary with keys:
                - 'strategy': Strategy type ("TB" or "FB")
                - 'direction': Trade direction ("BUY" or "SELL")
                - 'confirmations': Confirmation string ("V", "D", "VD", "NC")
                - 'range': Range identifier ("4H5M", "15M1M", etc.) or empty string
        """
        result = {
            'strategy': '',
            'direction': '',
            'confirmations': '',
            'range': ''
        }
        
        if not comment or '|' not in comment:
            return result
        
        parts = comment.split('|')
        
        if len(parts) >= 1:
            result['strategy'] = parts[0]
        if len(parts) >= 2:
            result['direction'] = parts[1]
        if len(parts) >= 3:
            result['confirmations'] = parts[2]
        if len(parts) >= 4:
            result['range'] = parts[3]
        
        return result
    
    @staticmethod
    def get_strategy_type(comment: str) -> str:
        """
        Extract strategy type from comment.
        
        Args:
            comment: Trade comment string
            
        Returns:
            Strategy type ("TB" or "FB") or empty string
        """
        parsed = TradeCommentParser.parse(comment)
        return parsed['strategy']
    
    @staticmethod
    def get_range_id(comment: str) -> str:
        """
        Extract range identifier from comment.
        
        Args:
            comment: Trade comment string
            
        Returns:
            Range identifier (e.g., "4H5M", "15M1M") or empty string
        """
        parsed = TradeCommentParser.parse(comment)
        return parsed['range']
    
    @staticmethod
    def get_direction(comment: str) -> str:
        """
        Extract trade direction from comment.
        
        Args:
            comment: Trade comment string
            
        Returns:
            Direction ("BUY" or "SELL") or empty string
        """
        parsed = TradeCommentParser.parse(comment)
        return parsed['direction']
    
    @staticmethod
    def get_confirmations(comment: str) -> str:
        """
        Extract confirmations from comment.
        
        Args:
            comment: Trade comment string
            
        Returns:
            Confirmations string ("V", "D", "VD", "NC") or empty string
        """
        parsed = TradeCommentParser.parse(comment)
        return parsed['confirmations']
    
    @staticmethod
    def has_volume_confirmation(comment: str) -> bool:
        """
        Check if trade had volume confirmation.
        
        Args:
            comment: Trade comment string
            
        Returns:
            True if volume was confirmed
        """
        confirmations = TradeCommentParser.get_confirmations(comment)
        return 'V' in confirmations
    
    @staticmethod
    def has_divergence_confirmation(comment: str) -> bool:
        """
        Check if trade had divergence confirmation.
        
        Args:
            comment: Trade comment string
            
        Returns:
            True if divergence was confirmed
        """
        confirmations = TradeCommentParser.get_confirmations(comment)
        return 'D' in confirmations
    
    @staticmethod
    def is_true_breakout(comment: str) -> bool:
        """
        Check if trade was a true breakout strategy.
        
        Args:
            comment: Trade comment string
            
        Returns:
            True if true breakout strategy
        """
        strategy = TradeCommentParser.get_strategy_type(comment)
        return strategy == StrategyConstants.STRATEGY_TYPE_TRUE_BREAKOUT
    
    @staticmethod
    def is_false_breakout(comment: str) -> bool:
        """
        Check if trade was a false breakout strategy.
        
        Args:
            comment: Trade comment string
            
        Returns:
            True if false breakout strategy
        """
        strategy = TradeCommentParser.get_strategy_type(comment)
        return strategy == StrategyConstants.STRATEGY_TYPE_FALSE_BREAKOUT
    
    @staticmethod
    def matches_strategy_and_range(comment: str, strategy_type: Optional[str] = None,
                                   range_id: Optional[str] = None) -> bool:
        """
        Check if comment matches given strategy type and/or range ID.
        
        Args:
            comment: Trade comment string
            strategy_type: Strategy type to match ("TB" or "FB"), or None to skip
            range_id: Range ID to match (e.g., "4H_5M"), or None to skip
            
        Returns:
            True if all provided criteria match
        """
        parsed = TradeCommentParser.parse(comment)
        
        # Check strategy type match
        if strategy_type is not None:
            if parsed['strategy'] != strategy_type:
                return False
        
        # Check range ID match (convert "4H_5M" to "4H5M" for comparison)
        if range_id is not None:
            normalized_range = range_id.replace('_', '')
            if parsed['range'] != normalized_range:
                return False
        
        return True

