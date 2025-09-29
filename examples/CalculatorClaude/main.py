from calculator import Calculator

def main() -> None:
    """Demonstrate calculator functionality with sample operations"""
    calc = Calculator()
    print("Calculator Demo:")
    print(f"10 + 5 = {calc.add(10, 5)}")
    print(f"10 - 5 = {calc.subtract(10, 5)}")
    print(f"10 * 5 = {calc.multiply(10, 5)}")
    print(f"10 / 5 = {calc.divide(10, 5)}")

if __name__ == "__main__":
    """Entry point when script is run directly"""
    main()
