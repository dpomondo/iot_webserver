def make_filename():
    from datetime import date
    month = date.today().strftime('%b_%Y')
    return f"{month}_temperatures.csv"
