from typing import List, Dict, Any

class Reducer:
    """
    A reusable reducer class for merging results from parallel nodes.
    Supports lists, maps, and typed partial states.
    """
    @staticmethod
    def reduce_lists(results: List[List[Any]]) -> List[Any]:
        """
        Merge multiple lists into a single list.
        """
        merged = []
        for result in results:
            merged.extend(result)
        return merged

    @staticmethod
    def reduce_maps(results: List[Dict[Any, Any]]) -> Dict[Any, Any]:
        """
        Merge multiple maps into a single map.
        """
        merged = {}
        for result in results:
            for key, value in result.items():
                if key not in merged:
                    merged[key] = []
                merged[key].append(value)
        return merged

    @staticmethod
    def reduce_typed_states(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge typed partial states into a single state.
        """
        merged = {}
        for result in results:
            for key, value in result.items():
                if key not in merged:
                    merged[key] = value
                elif isinstance(value, list) and isinstance(merged[key], list):
                    merged[key].extend(value)
                elif isinstance(value, dict) and isinstance(merged[key], dict):
                    merged[key].update(value)
        return merged