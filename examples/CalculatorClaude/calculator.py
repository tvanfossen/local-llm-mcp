from typing import Union

class Calculator:
    """A calculator class for performing basic arithmetic operations"""

    def add(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Add two numbers and return the result"""
        return a + b

    def subtract(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Subtract two numbers and return the result"""
        return a - b

    def multiply(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Multiply two numbers and return the result"""
        return a * b

    def divide(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Divide two numbers and return the result"""
        if not (b != 0):
            raise ValueError('Cannot divide by zero')
        return a / b
