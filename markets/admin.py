from django.contrib import admin

from .models import (
    CalculatedMarketPrice, City, CityMarketModifier, MarketActivityModifier,
    MarketEconomyConfig, MarketItemReference,
    MarketCategory, MarketModerationLog, MarketTransaction, MarketTypeConfig, MarketWithdrawal,
    MerchantCounter, MerchantCounterItem,
    PriceCalculationRun, TemporaryMarketModifier,
)


admin.site.register([
    MarketItemReference, City, MarketCategory, CityMarketModifier, MarketTypeConfig,
    MerchantCounter, MerchantCounterItem, CalculatedMarketPrice,
    MarketTransaction, MarketWithdrawal, MarketModerationLog, MarketEconomyConfig,
    MarketActivityModifier, PriceCalculationRun, TemporaryMarketModifier,
])
