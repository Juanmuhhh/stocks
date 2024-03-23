import os
import math

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Display the stocks information on this current user's index page
    stocks = db.execute(
        "SELECT symbol, name, SUM(shares) AS shares, price, SUM(total) AS total FROM users JOIN purchases ON users.id = purchases.user_id WHERE id = ? GROUP BY symbol", session["user_id"])

    rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    # Gets the total cash of the user and formats it to only have 2 decimal places
    cash = float(rows[0]["cash"])

    # Gets the value of all of the stocks plus the cash currently owned
    row_total = db.execute("SELECT total FROM purchases WHERE user_id = ?", session["user_id"])
    total = 0
    for row in row_total:
        for key, value in row.items():
            if value is not None:
                total += value

    new_total = (total + cash)

    return render_template("index.html", stocks=stocks, cash=cash, new_total=new_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    # If user reached route via POST
    if request.method == "POST":

        # Requires that user inputs stock symbol
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Requires valid symbol
        SYMBOL = request.form.get("symbol").upper()
        if lookup(SYMBOL) == None:
            return apology("Invalid Symbol", 400)

        # Requires for an input within shares
        if not request.form.get("shares"):
            return apology("must have valid entry", 400)

        # Requires that input of shares be a positive integer
        shares = request.form.get("shares")
        if "." in shares:
            return apology("can't be a fraction.", 400)

        # Requires that the shares be an integer and not a string
        for char in shares:
            if char.isalpha():
                return apology("must be a number and not a string.", 400)

        # Requires the shares to be a positive integer
        if float(shares) < 1:
            return apology("must be positive number", 400)

        # Makes variable for the price of a stock and checks to see if user has enough money
        original_price = lookup(SYMBOL)["price"]
        price = "{:.2f}".format(original_price)
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        if (float(price) * float(shares)) > cash[0]["cash"]:
            return apology("Not Enough Moneys!", 400)

        name = lookup(SYMBOL)["name"]

        total = float(shares) * float(price)

        shares_selected = int(request.form.get("shares"))
        shares_held = db.execute("SELECT list_shares FROM list WHERE user_id = ? AND symbol = ?", session["user_id"], SYMBOL)

        # Add into list of table if no shares are held
        if len(shares_held) == 0:
            db.execute("INSERT INTO list (symbol, list_shares, user_id) VALUES(?, ?, ?)",
                       SYMBOL, request.form.get("shares"), session["user_id"])
        else:
            shares_held = shares_held[0]["list_shares"]
            new_shares = shares_held + shares_selected
            db.execute("UPDATE list SET list_shares = ? WHERE user_id = ?", new_shares, session["user_id"])

        # Adds purchases into purchases table to display history
        db.execute("INSERT INTO purchases (symbol, shares, price, user_id, name, total) VALUES(?, ?, ?, ?, ?, ?)",
                   SYMBOL, request.form.get("shares"), price, session["user_id"], name, total)

        # Gets variable of new cash amount and updates the user table with new value
        old_cash = (cash[0]["cash"] - (original_price * float(shares)))
        new_cash = "{:.2f}".format(old_cash)

        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])

        return redirect("/")

    """Buy shares of stock"""
    return render_template("buy.html")


@app.route("/password", methods=["GET", "POST"])
@login_required
def password():

    if request.method == "POST":
        password = request.form.get("password")

        db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(password), session["user_id"])

        return redirect("/")

    else:
        return render_template("password.html")


@app.route("/history")
@login_required
def history():
    stocks = db.execute(
        "SELECT * FROM users JOIN purchases ON users.id = purchases.user_id WHERE id = ? ORDER BY transacted DESC", session["user_id"])

    return render_template("history.html", stocks=stocks)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    SYMBOL = {}

    if request.method == "POST":

        # If no symbol, return apology
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)

        # Stores symbol as a variable
        SYMBOL = request.form.get("symbol")

        # If symbol doesn't exist, return apology
        if lookup(SYMBOL) == None:
            return apology("INVALID SYMBOL", 400)

        # stores looks up the price, name, and symbol of the acronym
        price = lookup(SYMBOL)["price"]
        name = lookup(SYMBOL)["name"]
        symbol = lookup(SYMBOL)["symbol"]

        # returns the name symbol and price on the html "quoted"
        return render_template("quoted.html", name=name, symbol=symbol, price=price)

    # If get, asks them to input the acronym by taking them to the quote.html side
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    # Clears session if there was any
    session.clear()

    # User reached route via POST
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensures password match
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("password does not match", 400)

        # Query database for username
        check = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # If username exists, returns apology
        if len(check) == 1:
            return apology("username already exists", 400)

        # If username isn't taken, adds username and password to the database
        username = request.form.get("username")
        password = request.form.get("password")

        # Inserts the username and a hashed value of the password into the users database
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, generate_password_hash(password))

        # Selects the username in order to get the ID and set it below
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Assigns a user ID to specific user
        session["user_id"] = rows[0]["id"]

        # Redirects user to the homepage
        return redirect("/")

    # If user used the GET route, direct them to login page
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":

        # Ensures user input a stock symbol
        if not request.form.get("symbol"):
            return apology("Must select a symbol", 400)

        # Creates list of all symbols to check to see they have valid symbol
        symbol_list = []
        selection = request.form.get("symbol")
        symbols = db.execute("SELECT DISTINCT symbol FROM purchases WHERE user_id = ? GROUP BY symbol", session["user_id"])

        for row in symbols:
            symbol_list.append(row)

        if not any(d["symbol"] == selection for d in symbol_list):
            return apology("Symbol not in list", 400)

        # Requires user to input share
        if not request.form.get("shares"):
            return apology("must input a share value", 400)

        # Checks to see if share input by user is positive integer
        shares = request.form.get("shares")

        if shares.isnumeric() == False:
            return apology("selection must be an integer", 400)

        if int(shares) < 1:
            return apology("selection must be a positive integer", 400)

        # Checks to see if user has enough shares in their account
        stock_selected = db.execute("SELECT list_shares FROM list WHERE symbol = ? AND user_id = ?", selection, session["user_id"])

        for row in stock_selected:
            for key, value in row.items():
                if int(shares) > value:
                    return apology("not enough shares", 400)

        # Takes out how ever many shares and updates the user's cash

        # Gets total value of shares * price of stock
        share_value = db.execute("SELECT price FROM purchases WHERE symbol = ? AND user_id = ?", selection, session["user_id"])
        share_value = share_value[0]["price"] * int(shares)

        # Gets the users current cash
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        user_cash = user_cash[0]["cash"] + share_value

        # Updates user's cash on their user database
        db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash, session["user_id"])

        # Gets the user's shares
        new_shares = stock_selected[0]["list_shares"] - int(shares)
        print(new_shares)

        # Updates user's share in their purchases
        db.execute("UPDATE list SET list_shares = ? WHERE user_id = ? AND symbol = ?", new_shares, session["user_id"], selection)

        return redirect("/")

    else:
        # Creates empty list to input the different symbols to input on to html
        symbol_list = []

        # Gets all of the symbols grouped
        symbols = db.execute("SELECT DISTINCT symbol FROM purchases WHERE user_id = ? GROUP BY symbol", session["user_id"])
        for row in symbols:
            symbol_list.append(row)
        return render_template("sell.html", symbol_list=symbol_list)
