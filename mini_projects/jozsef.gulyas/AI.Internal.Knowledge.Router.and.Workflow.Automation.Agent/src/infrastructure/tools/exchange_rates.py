"""
Exchange rate tool for LLM function calling.

Uses Frankfurter API (https://www.frankfurter.app/) - free, no API key required.
"""
import httpx
from dataclasses import dataclass
from typing import Any


@dataclass
class ConversionResult:
    """Result of a currency conversion."""
    amount: float
    from_currency: str
    to_currency: str
    converted_amount: float
    rate: float


class ExchangeRateTool:
    """
    LLM tool for currency conversion.

    Uses Frankfurter API which provides free exchange rates from the European Central Bank.
    """

    BASE_URL = "https://api.frankfurter.app"

    # OpenAI function calling schema
    TOOL_DEFINITION = {
        "type": "function",
        "function": {
            "name": "convert_currency",
            "description": "Convert an amount from one currency to another using current exchange rates",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "The amount to convert"
                    },
                    "from_currency": {
                        "type": "string",
                        "description": "The source currency code (e.g., USD, EUR, GBP)"
                    },
                    "to_currency": {
                        "type": "string",
                        "description": "The target currency code (e.g., USD, EUR, GBP)"
                    }
                },
                "required": ["amount", "from_currency", "to_currency"]
            }
        }
    }

    async def convert_currency(
        self,
        amount: float,
        from_currency: str,
        to_currency: str
    ) -> ConversionResult:
        """
        Convert an amount from one currency to another.

        Args:
            amount: The amount to convert
            from_currency: Source currency code (e.g., "USD")
            to_currency: Target currency code (e.g., "EUR")

        Returns:
            ConversionResult with converted amount and rate
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/latest",
                params={
                    "amount": amount,
                    "from": from_currency,
                    "to": to_currency
                }
            )
            response.raise_for_status()
            data = response.json()

        converted_amount = data["rates"][to_currency]
        rate = converted_amount / amount if amount != 0 else 0

        return ConversionResult(
            amount=amount,
            from_currency=from_currency,
            to_currency=to_currency,
            converted_amount=converted_amount,
            rate=rate
        )

    async def execute(self, function_name: str, arguments: dict[str, Any]) -> str:
        """
        Execute the tool based on function name and arguments.

        This method is called by the LLM tool executor.
        """
        if function_name == "convert_currency":
            result = await self.convert_currency(
                amount=arguments["amount"],
                from_currency=arguments["from_currency"],
                to_currency=arguments["to_currency"]
            )
            return (
                f"{result.amount} {result.from_currency} = "
                f"{result.converted_amount:.2f} {result.to_currency} "
                f"(rate: {result.rate:.4f})"
            )
        raise ValueError(f"Unknown function: {function_name}")
