"""Pandera schemas for validating the cleaned retail dataset."""
import pandera.pandas as pa


class CleanSalesSchema(pa.DataFrameModel):
    """Schema that the cleaned CSV must satisfy.

    Run with:
        CleanSalesSchema.validate(df, lazy=True)

    Notes:
      - `quantity` allows negative values (returns/adjustments are valid).
      - `price_outlier_flag` is pipeline-added, not in raw data.
      - Customer name regex allows 1-3 capitalized words to handle
        cultures with single-word names (e.g. Madonna, Cher).
    """
    order_id: int = pa.Field(ge=1000, le=99999)
    order_date: pa.DateTime = pa.Field(nullable=True)
    customer_name: str = pa.Field(
        str_matches=r"^[A-Z][a-zA-Z]*(?: [A-Z][a-zA-Z]*){0,3}$"
    )
    city: str = pa.Field()
    country: str = pa.Field(isin=[
        "USA", "UK", "FRANCE", "GERMANY", "IRELAND", "JAPAN",
        "SINGAPORE", "AUSTRALIA", "INDIA", "CANADA",
    ])
    product: str = pa.Field()
    category: str = pa.Field(isin=["electronics", "furniture"])
    quantity: int = pa.Field(ge=-1000, le=10000)
    unit_price: float = pa.Field(ge=0.0, le=100_000_000.0)
    discount: float = pa.Field(ge=0.0, le=1.0)
    sales_rep_email: str = pa.Field(
        str_matches=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    customer_email: str = pa.Field(
        str_matches=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", nullable=True
    )
    payment_method: str = pa.Field(isin=["credit", "debit", "paypal"])
    notes: str = pa.Field(nullable=True)
    price_outlier_flag: bool = pa.Field()

    class Config:
        coerce = True
        strict = False  # we add price_outlier_flag


def validate(df, lazy=True):
    """Validate a cleaned DataFrame; raise SchemaError on failure."""
    return CleanSalesSchema.validate(df, lazy=lazy)