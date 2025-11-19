# src/config.py

# Base Economic Constants
INITIAL_CASH = 2000.0
INITIAL_DEBT = 0.0
INITIAL_SOAP = 50
INITIAL_PARTS = 2

# Machine Costs
COST_WASHER = 800.0
COST_DRYER = 600.0

# Inventory Costs
COST_SOAP_UNIT = 10.0     # Serves 10 loads
COST_PART = 150.0         # For repairs

# Service Prices (Base)
PRICE_WASH = 5.0
PRICE_DRY = 4.0
FAIR_MARKET_WASH = 5.0
FAIR_MARKET_DRY = 4.0

# Operational Costs
COST_UTILITY_PER_LOAD = 0.50
RENT_DAILY = 50.0

# Repair Costs
COST_REPAIR_CHEAP = 50.0
COST_REPAIR_PREMIUM = 200.0

# Mechanics Constants
MAX_CYCLES_PER_DAY = 10  # Max loads a machine can do in one day
SOAP_PER_LOAD = 0.1      # 1 unit of soap = 10 loads
