def make_filename():
    from datetime import date
    month = date.today().strftime("%Y-%b-%d")
    return f"{month}_temperatures.csv"
