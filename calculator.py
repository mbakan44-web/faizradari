from dataclasses import dataclass


@dataclass
class LoanOffer:
    bank_name: str
    monthly_rate: float  # Aylık akdi faiz oranı (ör. 3.89)
    principal: float     # Kredi tutarı (TL)
    months: int          # Vade (Ay)
    loan_type: str = "ihtiyac"  # "ihtiyac", "konut", "tasit"

    @property
    def effective_monthly_rate(self) -> float:
        """
        Türkiye BDDK/GİB mevzuatına göre:
        - İhtiyaç ve Taşıt kredisinde faiz üzerinden %15 KKDF + %15 BSMV (toplam %30) vergi alınır.
        - Konut kredisinde KKDF ve BSMV %0'dır.
        """
        r = self.monthly_rate / 100.0
        if self.loan_type in ("ihtiyac", "tasit"):
            return r * 1.30
        return r

    @property
    def monthly_installment(self) -> float:
        """Aylık eşit taksit tutarı (TL)."""
        r_eff = self.effective_monthly_rate
        if r_eff == 0:
            return self.principal / self.months
        factor = (1 + r_eff) ** self.months
        return self.principal * (r_eff * factor) / (factor - 1)

    @property
    def allocation_fee(self) -> float:
        """
        BDDK yasal kredi tahsis ücreti (dosya masrafı):
        Anaparanın binde 5'i (%0.5) + ihtiyaç/taşıt kredisinde bunun üzerinden %15 BSMV (%0.575).
        """
        if self.monthly_rate == 0:
            return 0.0
        if self.loan_type in ("ihtiyac", "tasit"):
            return self.principal * 0.00575
        return self.principal * 0.005

    @property
    def total_repayment(self) -> float:
        """Tahsis ücreti dahil toplam cebinizden çıkacak net geri ödeme (TL)."""
        return (self.monthly_installment * self.months) + self.allocation_fee

    @property
    def total_interest_and_tax(self) -> float:
        """Toplam ödenen faiz + vergi + masraf farkı."""
        return self.total_repayment - self.principal


@dataclass
class DepositOffer:
    bank_name: str
    annual_rate: float   # Yıllık mevduat faiz oranı (ör. 52.0)
    principal: float     # Anapara (TL)
    days: int = 32       # Vade gün sayısı
    withholding_tax: float = 0.10  # %10 Stopaj oranı

    @property
    def gross_return(self) -> float:
        return self.principal * (self.annual_rate / 100.0) * (self.days / 365.0)

    @property
    def net_return(self) -> float:
        return self.gross_return * (1.0 - self.withholding_tax)

    @property
    def total_balance(self) -> float:
        return self.principal + self.net_return


@dataclass
class SpreadOffer:
    bank_name: str
    asset: str           # "USD" veya "ALTIN"
    buy_price: float     # Banka Alış (TL)
    sell_price: float    # Banka Satış (TL)
    updated_time: str = ""

    @property
    def spread_tl(self) -> float:
        """Satış - Alış TL Makas Farkı."""
        return max(0.0, self.sell_price - self.buy_price)

    @property
    def spread_pct(self) -> float:
        """Yüzdesel Makas Oranı (%)."""
        if self.buy_price <= 0:
            return 0.0
        return ((self.sell_price - self.buy_price) / self.buy_price) * 100.0


def format_tl(amount: float) -> str:
    """123456.78 -> '123.457 TL' formatına çevirir."""
    rounded = round(amount)
    return f"{rounded:,.0f}".replace(",", ".") + " TL"


def format_price(amount: float, decimals: int = 2) -> str:
    """Kuruşlu döviz/altın fiyatı formatlar (ör. 49,92 TL veya 6.453,20 TL)."""
    formatted = f"{amount:,.{decimals}f}"
    # İngiliz binlik/ondalık ayıracını Türkçe formata çevir
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} TL"
