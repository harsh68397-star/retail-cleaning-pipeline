# Data Dictionary — `retail_sales_clean.csv`

The output of `python src/pipeline.py`. Every column's meaning,
type, and the cleaning rule applied.

| Column | Type | Description | Cleaning rule |
|---|---|---|---|
| `order_id` | Int64 | Unique order identifier | Coerced from text — invalid → NaN |
| `order_date` | datetime64[ns] | Day the order was placed | Parsed from mixed formats (5+ styles) |
| `customer_name` | string | Customer full name | Title-cased, whitespace trimmed |
| `city` | string | Customer city | Title-cased, whitespace trimmed |
| `country` | string | Customer country (uppercase) | Normalized to uppercase ISO-style |
| `product` | string | Product name | Whitespace trimmed |
| `category` | string | Product category | Lowercased to canonical form |
| `quantity` | Int64 | Items purchased (allows negative for returns) | Numeric coercion; null on parse fail |
| `unit_price` | float64 | Price per unit in USD | Stripped of `$`, quotes, commas |
| `discount` | float64 | Fractional discount (0.0 – 1.0) | Missing → 0.0 |
| `sales_rep_email` | string | Sales rep email | Validated against email regex |
| `customer_email` | string | Customer email | Validated against email regex |
| `payment_method` | string | credit / debit / paypal | Lowercased + whitelist |
| `notes` | string | Free-form notes | Trimming only |
| `price_outlier_flag` | bool | True if unit_price outside 3×IQR | Computed, not in raw data |

