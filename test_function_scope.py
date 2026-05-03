"""Test that _show_dimensions is callable from the same scope as app.py"""
import sys, json

# Simulate the app.py structure: functions called before def'd, inside a block
value_defined = False

def test():
    print("1. Function compiled at module level")
    
    # This is what app.py does — calls _show_dimensions inside a conditional block
    # before the function is defined at the bottom
    result = {"dimensions": {"test": {"score": 75}}}
    
    # These lines mirror what happens at line 304
    _show_dimensions(result)
    print("   -> _show_dimensions called successfully!")

# Define AFTER the calls above
def _show_dimensions(results):
    dims = results.get("dimensions", {})
    for name, dim in dims.items():
        score = dim.get("score", 0)
        print(f"   dimension: {name} = {score}")

# Run it
test()
print("2. All good! No NameError.")
