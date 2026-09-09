# 51 — Official Udyam Domain Specification

## 1. MSME Classification Thresholds (Effective 01.04.2025 / 2026)

| Category | Investment in Plant & Machinery / Equipment | Annual Turnover |
| :--- | :--- | :--- |
| **MICRO** | $\le$ ₹2.5 Crore | $\le$ ₹10 Crore |
| **SMALL** | $\le$ ₹25 Crore | $\le$ ₹100 Crore |
| **MEDIUM** | $\le$ ₹125 Crore | $\le$ ₹500 Crore |

*Note: In accordance with statutory rules, export turnover of goods and services is excluded when calculating the turnover threshold.*

## 2. 10 Discrete Udyam Workflow Types

1. **`NEW_UDYAM`**: Complete new enterprise registration.
2. **`UDYAMI_LOGIN`**: Authentication via UAN + registered Mobile + OTP.
3. **`UDYAM_UPDATE`**: Update existing registration details, address, units, NIC activities.
4. **`UDYAM_CANCEL`**: Formal cancellation request with reason recording.
5. **`PRINT_CERTIFICATE`**: Download verified Udyam Certificate with dynamic QR code.
6. **`VERIFY_UDYAM`**: Public verification of enterprise validity by UAN.
7. **`VERIFY_UAM`**: Legacy Udyog Aadhaar Memorandum verification.
8. **`FORGOT_NUMBER`**: Recovery of lost Udyam/UAM number via Aadhaar/Mobile OTP.
9. **`UAM_MIGRATION`**: Direct migration of legacy UAM to permanent Udyam.
10. **`ASSISTED_UAM_MIGRATION`**: Assisted migration path via DIC / Facilitation Desk.

## 3. Multiple Units & NIC Activities Support
- **Units**: Modeled as `application_units` relation with separate address and state/district for each manufacturing plant or service location.
- **NIC 2008 Activities**: Modeled as `nic_suggestions` and `application_requirements` allowing multiple 2-digit, 4-digit, and 5-digit codes per registration without duplicate applications.
