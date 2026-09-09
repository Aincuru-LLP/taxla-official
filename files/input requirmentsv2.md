

Below is the corrected **complete official Udyam ecosystem as of 31 August 2026**.

---

# 1. FIRST: THE OFFICIAL WEBSITE

The only official Udyam Registration portal is:

[Official Udyam Registration Portal — Government of India](https://udyamregistration.gov.in/?utm_source=chatgpt.com)

The portal itself says that, except for this Government portal and Government Single Window Systems, **no private online/offline website, agency, person or service is authorized to perform MSME registration**. It also states that Udyam registration is **free, paperless and self-declaration based**. ([Udyam Registration][1])

So the website you previously showed me (`udyamregistration-msme.com`) should **not** be treated as the source of truth.

---

# 2. THE OFFICIAL WEBSITE HAS MORE THAN JUST "NEW REGISTRATION"

This is the first major thing I want you to understand.

The current official homepage has:

```text
UDYAM PORTAL
│
├── INFORMATION
│   ├── NIC Code
│   ├── Important
│   ├── Benefits
│   ├── Circulars & Orders
│   ├── Sample Form
│   ├── Registration Bulletins
│   └── Metadata
│
├── PRINT / VERIFY
│   ├── Print Udyam Certificate
│   ├── Verify Udyam Registration
│   ├── Print UAM Certificate
│   ├── Verify Udyog Aadhaar
│   ├── Print UAM Application
│   └── Forgot Udyam/UAM Number
│
├── UPDATE / CANCEL
│
├── LOGIN
│   ├── Udyami Login
│   ├── Officer Login
│   ├── EFC Login
│   └── NSSH Officer Login
│
└── REGISTRATION
    ├── New Registration
    ├── UAM Migration
    ├── Assisted UAM Migration
    └── Udyam Assist Platform
```

I verified these menu items directly on the current homepage. ([Udyam Registration][1])

**This is the complete portal architecture you should use for your specification.**

---

# 3. CURRENT MSME CLASSIFICATION

This was changed from 1 April 2025 and is still the current classification shown by the official portal.

| Category   | Investment in plant/machinery/equipment | Annual turnover |
| ---------- | --------------------------------------: | --------------: |
| **Micro**  |                            ≤ ₹2.5 crore |     ≤ ₹10 crore |
| **Small**  |                             ≤ ₹25 crore |    ≤ ₹100 crore |
| **Medium** |                            ≤ ₹125 crore |    ≤ ₹500 crore |

The official portal explicitly shows the old → new thresholds and the effective change from 1 April 2025. ([Udyam Registration][1])

So **do not use the old ₹1/₹10/₹50 crore investment limits** in your system.

---

# 4. NEW UDYAM REGISTRATION

This is the flow you were originally asking about.

[Official New Udyam Registration Form](https://udyamregistration.gov.in/UdyamRegistration.aspx?utm_source=chatgpt.com)

The live page currently shows:

```text
1. Aadhaar Verification
2. PAN Verification
3. Basic Details
4. Official Address
5. Plant/Unit Details
6. Other Details
```

I verified this directly on the live page. ([Udyam Registration][2])

---

# 5. STAGE 1 — AADHAAR VERIFICATION

The first screen asks for:

### Required

* Aadhaar number
* Name of entrepreneur as per Aadhaar
* Aadhaar consent

Then:

```text
Validate & Generate OTP
        ↓
Aadhaar OTP
        ↓
Verify
```

The official live page explicitly says Aadhaar is required. ([Udyam Registration][2])

### Who's Aadhaar?

This is conditional:

| Entity         | Aadhaar of           |
| -------------- | -------------------- |
| Proprietorship | Proprietor           |
| Partnership    | Managing partner     |
| HUF            | Karta                |
| Company        | Authorised signatory |
| LLP            | Authorised signatory |
| Cooperative    | Authorised signatory |
| Society        | Authorised signatory |
| Trust          | Authorised signatory |

For companies, LLPs, cooperative societies, societies and trusts, the official form also requires PAN and GSTIN as applicable. ([Udyam Registration][2])

### Important privacy point

The official Aadhaar consent says the Ministry has informed the applicant that the Aadhaar data will not be stored/shared for this purpose. ([Udyam Registration][3])

---

# 6. STAGE 2 — PAN VERIFICATION

This is **more important than I originally described**.

After Aadhaar verification, the form asks for the organisation type and PAN-related information.

The official sample/process document shows:

### Organisation type

```text
Proprietary
Partnership
HUF
Company
LLP
Cooperative
Society
Trust
etc.
```

### PAN

* Do you have PAN?
* PAN number
* PAN verification/consent

The PAN consent allows the Ministry to use information from Income Tax Returns, GST returns and other government organisations for MSME classification and official purposes. ([Udyam Registration][4])

### Critical validation

If the PAN already has a Udyam registration, the portal can display:

> **“Udyam Registration has already done through this PAN.”**

This means your automation must have a **duplicate-registration detection state** before continuing. ([Udyam Registration][4])

---

# 7. VERY IMPORTANT: PAN/GST/ITR DATA IS NOT SIMPLY USER-ENTERED

The official portal says:

* PAN-linked information is obtained from government databases.
* GST-linked information is obtained from government databases.
* The system integrates with Income Tax and GSTIN systems.
* Investment and turnover information can be populated from those sources. ([Udyam Registration][1])

So your system should model:

```text
USER INPUT
    ↓
PAN
    ↓
Government verification
    ↓
ITR data
    ↓
GST data
    ↓
Udyam classification
```

rather than:

```text
User types turnover
      ↓
Trust blindly
```

---

# 8. STAGE 3 — BASIC DETAILS

This is where I found several fields that deserve to be explicitly included in your specification.

The official Udyam application document lists:

### 5. Entrepreneur name

Name as per PAN/Aadhaar.

### 6. Mobile number

Registered contact number.

### 7. Email

Registered email.

### 8. Social category

```text
General
SC
ST
OBC
```

### 9. Gender

```text
Male
Female
Others
```

### 10. Specially Abled / Divyang

```text
Yes
No
```

### 11. Name of Enterprise

The official form says this is auto-filled from PAN verification where applicable and can be editable. ([Udyam Registration][5])

---

# 9. OWNERSHIP CATEGORY RULE

The official form contains an important ownership rule that I previously didn't explain.

It provides ownership thresholds/guidance for categories such as:

* OBC
* SC
* ST
* Women

depending on the entity structure and ownership/share/member/contribution basis.

For a proprietorship, the enterprise's category follows the social category of the owner. ([Udyam Registration][5])

This matters if you're building an AI questionnaire because you shouldn't ask the same ownership questions for every legal structure.

---

# 10. STAGE 4 — PLANT / UNIT DETAILS

This is **not just one plant field**.

The official form allows:

```text
Add Unit
Add Unit
Add Unit
...
```

Each unit has:

* Unit name
* Flat/Door/Block
* Building/premises
* Village/Town
* Block
* Road/Street/Lane
* City
* PIN
* State
* District

The official application demonstrates multiple plant/unit entries and an "Add More" mechanism. ([Udyam Registration][4])

So your data model should be:

```text
enterprise
   │
   ├── unit[]
   │     ├── name
   │     ├── address
   │     ├── state
   │     └── district
   │
   ├── unit[]
   └── unit[]
```

**Do not design `plant_address` as a single field.**

---

# 11. STAGE 5 — OFFICIAL ADDRESS

Separate from plant/unit addresses, there is the **Official Address of Enterprise**.

The official form includes:

* Flat/Door/Block No.
* Name of Premises/Building
* Village/Town
* Block
* Road/Street/Lane
* City
* PIN
* State
* District

([Udyam Registration][5])

So:

```text
OFFICIAL ADDRESS
        ≠
PLANT / UNIT ADDRESS
```

Your automation needs to treat them separately.

---

# 12. PREVIOUS MSME REGISTRATION

Another field that shouldn't be missed:

### Previous EM-II/UAM Registration Number, if any

Options include:

```text
N/A
EM-II
Previous UAM
```

The official form explicitly contains this field. ([Udyam Registration][5])

This connects the new application to the old MSME registration ecosystem.

---

# 13. STATUS OF ENTERPRISE

The official form asks:

### Date of incorporation/registration

and:

### Whether production/business commenced?

```text
Yes
No
```

If yes:

### Date of commencement

([Udyam Registration][5])

So your questionnaire needs:

```text
incorporation_date
business_commenced
commencement_date
```

---

# 14. BANK DETAILS

This is another field I want to explicitly correct/add.

The official application includes:

* Bank name
* IFSC code
* Bank account number

([Udyam Registration][5])

So:

```text
Bank
├── Bank Name
├── IFSC
└── Account Number
```

---

# 15. MAJOR ACTIVITY

The form asks for the major activity of the unit.

The official application currently exposes:

```text
Manufacturing
Services
```

and the NIC section additionally exposes **Trading** as an activity type. ([Udyam Registration][5])

This distinction matters.

---

# 16. NIC CODE — VERY IMPORTANT

The business activity is mapped to **National Industrial Classification (NIC-2008)**.

The official form provides:

```text
Search NIC Code
        OR
NIC 2 Digit
        ↓
NIC 4 Digit
        ↓
NIC 5 Digit
```

The form explicitly says one or more activities can be added. ([Udyam Registration][5])

And the official homepage states that one enterprise must not file multiple Udyam registrations, but **multiple activities can be specified/added under the same registration**. ([Udyam Registration][1])

### For your AI system

This should become:

```text
User:
"We manufacture PVC pipes and also trade plumbing materials."

AI:
Understands two activities

        ↓

NIC Activity 1
Manufacturing → appropriate NIC

NIC Activity 2
Trading → appropriate NIC

        ↓

User confirms

        ↓

One Udyam registration
```

But the AI should **suggest**, not hallucinate NIC codes. Your production system should validate against an authoritative NIC dataset.

---

# 17. EMPLOYMENT

The official application includes:

```text
Male
Female
Others
Total
```

The total is derived from the categories. ([Udyam Registration][5])

There is also an explicit declaration:

> the applicant is aware of the Child & Adolescent Labour (Prohibition and Regulation) Act and declares that no child is employed in the enterprise. ([Udyam Registration][5])

**This declaration was something I had missed previously.**

Your automation should include it in the final compliance/declaration layer.

---

# 18. INVESTMENT

The form deals with investment in:

> Plant and Machinery OR Equipment

The application structure includes:

```text
Written Down Value
        ↓
Less eligible exclusions
        ↓
Net Investment
```

The exclusions include costs associated with things such as pollution control, R&D and industrial safety devices as specified by the form/rules. ([Udyam Registration][5])

However, **do not hard-code the old financial year shown in the sample PDF**.

That's important.

The official sample PDF contains historical examples such as FY 2020–21/2021–22. The live portal now operates against current government data and the current MSME thresholds. ([Udyam Registration][5])

So:

> **Use the PDF for field structure, not for current financial-year values or current thresholds.**

---

# 19. TURNOVER

The form also has:

```text
Total Turnover
Export Turnover
Net Turnover
```

and government data integration.

The official portal states that PAN/GST-linked investment and turnover data is obtained from government databases. ([Udyam Registration][1])

The application documentation also explains that ITR/GST data can auto-populate these figures, with self-declaration used in certain situations. ([Udyam Registration][5])

---

# 20. EXTRA QUESTIONS THAT I MISSED BEFORE

This is probably the biggest missing piece from my previous answer.

The official application document includes additional optional-interest questions:

### GeM

> Are you interested in getting registered on Government e-Market (GeM) Portal?

### TReDS

> Are you interested in getting registered on TReDS Portals?

### NCS

> Are you interested in getting registered on National Career Service (NCS) Portal?

### NSIC B2B

> Are you interested in availing/registering on NSIC B2B Portal?

### Free `.IN` domain + business email

The official application document lists these additional questions. ([Udyam Registration][5])

So your automation data model should have:

```text
interested_in_gem
interested_in_treds
interested_in_ncs
interested_in_nsic_b2b
interested_in_in_domain
```

**Do not forget these if you're trying to replicate the complete government form.**

---

# 21. DISTRICT INDUSTRIES CENTRE — DIC

The official application also contains:

> **District Industries Centre**

with a DIC selection. ([Udyam Registration][5])

This is another field I didn't explicitly include before.

Your system therefore needs:

```text
State
   ↓
District
   ↓
DIC
```

rather than asking the user to type a random DIC name.

---

# 22. FINAL DECLARATION

At the bottom, the applicant declares that:

* information provided is true to the best of their knowledge;
* evidence/proof may be produced if required for verification.

Then:

```text
Submit & Get Final OTP
```

The official application shows this exact final declaration/OTP stage. ([Udyam Registration][5])

---

# 23. OTP + FINAL SUBMISSION

Conceptually:

```text
Complete application
       ↓
Declaration
       ↓
Submit
       ↓
Final OTP
       ↓
OTP verification
       ↓
Registration processing
```

Do not confuse this with the **login OTP**. They are separate events.

---

# 24. WHAT HAPPENS AFTER SUBMISSION?

Here is another nuance.

The official sample/process document shows a **reference number** after successful submission and describes certificate issuance after verification/data processing. ([Udyam Registration][4])

However, a government FAQ hosted by an MSME office says that after successful submission, the Udyam Registration Certificate is issued online and can be downloaded through the Udyami Login. ([MSME Jaipur][6])

Therefore, for your product specification, don't promise:

> "Certificate always appears instantly."

Instead use the safer state machine:

```text
SUBMITTED
   ↓
PROCESSING / DATA VERIFICATION
   ↓
REGISTERED
   ↓
CERTIFICATE AVAILABLE
```

That's much better engineering.

---

# 25. UDYAM REGISTRATION NUMBER

Once registration is completed, the enterprise gets a **permanent Udyam Registration Number**.

The portal says the number is permanent and there is **no renewal requirement**. ([Udyam Registration][1])

The Udyami Login specifies the format as:

```text
UDYAM-XX-00-0000000
```

and describes it as a 19-character registration number. ([Udyam Registration][7])

---

# 26. UDYAM CERTIFICATE

After successful registration:

```text
Udyam Registration Number
          ↓
Udyam Registration Certificate
```

The certificate is online and contains a **dynamic QR code** through which the enterprise information can be accessed on the official portal. ([Udyam Registration][1])

---

# 27. UDYAMI LOGIN

This was your original confusion.

The registration page is **NOT the login page**.

The official Udyami Login is:

[Official Udyami Login](https://udyamregistration.gov.in/Udyam_Login.aspx?utm_source=chatgpt.com)

It asks for:

### 1. Udyam Registration Number

```text
UDYAM-XX-00-0000000
```

### 2. Mobile number

The mobile number used in the application.

### 3. OTP option

```text
OTP on Mobile
OR
OTP on Email
```

### 4. Captcha

Then:

```text
Validate & Generate OTP
        ↓
Receive OTP
        ↓
Enter OTP
        ↓
Validate OTP & Login
```

The official login page confirms this exact flow. ([Udyam Registration][7])

---

# 28. UPDATE / CANCEL — IMPORTANT THING I MISSED

**This is the biggest thing missing from my previous answer.**

The current official homepage explicitly has:

> **Update/Cancel Udyam Registration**

as a separate portal function. ([Udyam Registration][1])

It is accessed through the Udyami authentication flow.

Conceptually:

```text
Existing Udyam
      ↓
Udyam Number
      +
Registered Mobile
      ↓
OTP
      ↓
Udyami Login
      ↓
Update / Cancel
```

The official government FAQ confirms that Udyam registration can be updated/cancelled through the portal. ([MSME Jaipur][6])

### Update

Typical workflow:

```text
Login
 ↓
Udyam Registration Details
 ↓
Edit Details
 ↓
Modify permitted information
 ↓
Update
 ↓
Confirmation
 ↓
Updated certificate
```

Government-hosted/officially referenced guidance confirms the update/cancellation functionality. ([MSME Jaipur][6])

### Cancellation

Cancellation is a separate operation:

```text
Login
 ↓
Cancellation
 ↓
Select cancellation reason
 ↓
Provide reason
 ↓
Submit cancellation
 ↓
Government processing
 ↓
Cancellation decision
```

A government FAQ also confirms that cancellation is available and that pending cancellation can be escalated through the relevant DFO. ([MSME Jaipur][6])

**For your automation product, cancellation should absolutely be a separate workflow—not just a boolean `is_active=false`.**

---

# 29. PRINT / VERIFY

The official portal has an entire Print/Verify ecosystem. ([Udyam Registration][1])

## A. Print Udyam Certificate

Used to retrieve/print the certificate.

## B. Verify Udyam Registration

Used by someone who wants to verify a Udyam registration.

## C. Print UAM Certificate

For legacy Udyog Aadhaar registrations.

## D. Verify Udyog Aadhaar

For legacy UAM verification.

## E. Print UAM Application

Retrieves old UAM application information.

## F. Forgot Udyam/UAM Number

Used when the enterprise doesn't know its registration number.

These are all separate functions. ([Udyam Registration][1])

---

# 30. FORGOT UDYAM NUMBER

[Official Forgot Udyam/UAM Number](https://udyamregistration.gov.in/ForgotRegNo.aspx?utm_source=chatgpt.com)

The user chooses:

```text
Registration type
├── Udyog Aadhaar Memorandum
└── Udyam Registration
```

Then:

```text
OTP method
├── Mobile
└── Email
```

Then:

```text
Registered Mobile/Email
        ↓
Validate & Generate OTP
        ↓
OTP
        ↓
Validate OTP
        ↓
Registered number(s)
```

The official page explicitly confirms that successful OTP verification returns the registered number(s). ([Udyam Registration][8])

---

# 31. UAM MIGRATION

This is **not new registration**.

It is for businesses that already have an old **Udyog Aadhaar Memorandum (UAM)**.

[Official UAM → Udyam Migration](https://udyamregistration.gov.in/UdyamRegistrationExist.aspx?utm_source=chatgpt.com)

The current official page asks for:

* Udyog Aadhaar Number
* OTP method

```text
OTP on Mobile used in UAM
OR
OTP on Email used in UAM
```

([Udyam Registration][9])

Conceptually:

```text
Old UAM
   ↓
UAM Number
   ↓
OTP
   ↓
Verify
   ↓
Migration
   ↓
Udyam
```

---

# 32. ASSISTED UAM MIGRATION

Separate from normal UAM migration.

[Official Assisted UAM Migration](https://udyamregistration.gov.in/Udyam_AssistedMigration.aspx?utm_source=chatgpt.com)

The official portal explicitly labels this:

> For those already having UAM registration under assisted filling.

It uses:

* Udyog Aadhaar Number
* Mobile/email from UAM
* OTP verification

([Udyam Registration][10])

So your system should have **two separate migration workflows**.

---

# 33. UDYAM ASSIST PLATFORM — UAP

This is another thing that must not be merged with normal Udyam.

The official portal currently has:

> **Udyam Assist Platform (UAP) — Informal Micro Enterprises Registration**

and links to the separate official domain:

[Official Udyam Assist Platform](https://udyamassist.gov.in/?utm_source=chatgpt.com)

The official Udyam homepage explicitly distinguishes UAP from normal Udyam registration. ([Udyam Registration][1])

So:

```text
NORMAL UDYAM
    ↓
Formal MSME registration

UAP
    ↓
Informal Micro Enterprise formalisation
```

The official circular archive says UAP was launched to bring informal micro enterprises into the formal system, including for Priority Sector Lending. ([Udyam Registration][11])

---

# 34. OFFICER LOGINS

The official portal also has:

```text
Officer's Login
EFC's Login
NSSH Officer's Login
Udyami Login
```

These are **not customer registration accounts**. ([Udyam Registration][1])

For your commercial automation platform, the relevant one is primarily:

```text
Udyami Login
```

unless you're explicitly building a government/official workflow.

---

# 35. NIC CODE SECTION

The official website has a dedicated **NIC Code** section in the top navigation. ([Udyam Registration][1])

This should become an important component of your automation:

```text
Business description
       ↓
AI classification
       ↓
NIC search
       ↓
2-digit
       ↓
4-digit
       ↓
5-digit
       ↓
User confirmation
```

Again: **AI can recommend; the authoritative code list must validate.**

---

# 36. OFFICIAL DOCUMENTATION / RULES

The portal also has:

* Important
* Benefits
* Circulars & Orders
* Sample Form
* Udyam Registration Bulletins
* Metadata Compliance
* Parliament questions/documents

The current homepage exposes these resources. ([Udyam Registration][1])

This matters because **the website changes over time**.

The official circular page currently lists, among other things:

* revised MSME definition effective from 1 April 2025;
* DigiLocker acceptance of Udyam Registration Certificate;
* UAP formalisation;
* grievance/update/cancellation actions. ([Udyam Registration][11])

---

# 37. IMPORTANT: THE OFFICIAL SAMPLE PDF IS NOT THE SAME AS THE CURRENT LIVE FORM

This is a subtle but **very important** correction.

The official website provides an application PDF that shows the detailed field structure. ([Udyam Registration][5])

But parts of the PDF contain **historical financial-year examples** such as:

```text
2018-19
2020-21
2021-22
```

Those are examples/documentation from earlier versions.

The **live portal and current government rules are authoritative for 2026**, not those historical example years. The current portal shows the revised 2025 MSME thresholds and current system. ([Udyam Registration][1])

So for your product:

> **Use the live portal for current behavior. Use the official PDF for discovering the complete field structure.**

That is the correct approach.

---

# 38. THE COMPLETE CURRENT NEW-REGISTRATION DATA MODEL

If you're building your automation database, I would capture this:

```text
APPLICANT
├── Aadhaar
├── Aadhaar name
├── Mobile
├── Email
├── Social category
├── Gender
└── Divyang status

ENTITY
├── Organisation type
├── PAN
├── GSTIN
├── Enterprise name
├── Incorporation date
├── Commencement status
└── Commencement date

OWNERSHIP
├── Category
├── Ownership/share information where applicable
└── Women/SC/ST/OBC classification

ADDRESS
├── Flat/Door/Block
├── Building
├── Village/Town
├── Block
├── Road/Street/Lane
├── City
├── State
├── District
└── PIN

UNITS[]
├── Unit name
├── Address
├── State
├── District
└── PIN

LEGACY
├── Previous EM-II?
├── Previous UAM?
└── UAM number

BANK
├── Bank name
├── IFSC
└── Account number

BUSINESS
├── Major activity
├── Manufacturing/Services/Trading
└── NIC activities[]

EMPLOYMENT
├── Male
├── Female
├── Others
└── Total

FINANCIAL
├── Investment
├── Eligible exclusions
├── Net investment
├── Total turnover
├── Export turnover
└── Net turnover

OPTIONAL GOVERNMENT SERVICES
├── GeM
├── TReDS
├── NCS
├── NSIC B2B
└── .IN domain/business email

ADMINISTRATIVE
├── District Industries Centre
└── Declaration

VERIFICATION
├── Aadhaar OTP
├── PAN verification
├── GST verification
├── ITR verification
└── Final OTP

OUTPUT
├── Reference/status
├── Udyam Registration Number
└── Udyam Registration Certificate
```

The official application document supports these field groups, including the extra service questions and DIC selection. ([Udyam Registration][5])

---

# 39. THE COMPLETE UDYAM STATE MACHINE

For **AINCURU × TAXLA**, I would model the government process like this:

```text
                    START
                      │
                      ▼
             BUSINESS ELIGIBILITY
                      │
                      ▼
              CHOOSE WORKFLOW
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
      NEW           OLD UAM         UAP
    UDYAM          MIGRATION
        │
        ▼
   AADHAAR OTP
        │
        ▼
   PAN VERIFICATION
        │
        ├── Already registered?
        │          │
        │          └── STOP / LOGIN
        │
        ▼
    BASIC DETAILS
        │
        ▼
    UNIT DETAILS
        │
        ▼
   OFFICIAL ADDRESS
        │
        ▼
   BUSINESS DETAILS
        │
        ▼
      NIC CODE
        │
        ▼
    EMPLOYMENT
        │
        ▼
   FINANCIAL DATA
        │
        ▼
 OPTIONAL SERVICES
        │
        ▼
       DIC
        │
        ▼
    DECLARATION
        │
        ▼
     FINAL OTP
        │
        ▼
      SUBMIT
        │
        ▼
    PROCESSING
        │
        ▼
   UDYAM NUMBER
        │
        ▼
     CERTIFICATE
        │
        ├───────────────┐
        ▼               ▼
      LOGIN        PRINT / VERIFY
        │
        ├── UPDATE
        │
        ├── PRINT
        │
        └── CANCEL
```

---

# 40. COMPLETE OFFICIAL PORTAL MAP

So, finally, this is the map I would freeze for your project:

```text
                    UDYAMREGISTRATION.GOV.IN
                              │
 ┌────────────────────────────┼──────────────────────────────┐
 │                            │                              │
 ▼                            ▼                              ▼
REGISTRATION             EXISTING BUSINESS             INFORMATION
 │                            │                              │
 ├─ New Udyam                 ├─ Udyami Login                ├─ NIC Code
 │                            ├─ Update                       ├─ Important
 ├─ UAM Migration             ├─ Cancel                       ├─ Benefits
 │                            ├─ Print Certificate             ├─ Circulars
 ├─ Assisted Migration        ├─ Verify                       ├─ Sample Form
 │                            ├─ Forgot Number                 ├─ Bulletins
 └─ UAP → udyamassist.gov.in  ├─ Print UAM                     └─ Metadata
                              └─ Verify UAM

                              │
                              ▼
                           OFFICIAL
                          ECOSYSTEM
                              │
               ┌──────────────┼───────────────┐
               ▼              ▼               ▼
             UDYAMI         OFFICER          EFC/NSSH
             LOGIN          LOGIN             LOGIN
```

The current official homepage confirms this overall structure. ([Udyam Registration][1])

---

# 41. THE MOST IMPORTANT CORRECTIONS TO MY PREVIOUS ANSWER

I want to explicitly call these out so you don't build your system from an incomplete specification:

### I previously under-emphasized:

**1. Update/Cancel Udyam Registration**
→ It is an official portal function. ([Udyam Registration][1])

**2. Ownership/category logic**
→ The official form has ownership/share/member/contribution guidance. ([Udyam Registration][5])

**3. Divyang field**
→ Official application includes it. ([Udyam Registration][5])

**4. Previous EM-II/UAM field**
→ Official application includes it. ([Udyam Registration][5])

**5. Bank details**
→ Bank name + IFSC + account number. ([Udyam Registration][5])

**6. Child-labour declaration**
→ Explicit declaration exists in the official application. ([Udyam Registration][5])

**7. GeM/TReDS/NCS/NSIC/.IN questions**
→ These are in the official application documentation. ([Udyam Registration][5])

**8. DIC selection**
→ Explicit application field. ([Udyam Registration][5])

**9. Multiple units**
→ Multiple plant/unit locations are supported. ([Udyam Registration][4])

**10. Multiple NIC activities**
→ One registration can contain multiple activities. ([Udyam Registration][1])

**11. UAP is a separate ecosystem**
→ It is not simply another name for normal Udyam. ([Udyam Registration][1])

**12. Historical PDF vs current portal**
→ The official PDF contains historical examples; current rules must come from the live portal/current notifications. ([Udyam Registration][5])

---

## Bottom line

If you're building **AINCURU × TAXLA's Udyam/MSME automation**, **this is the specification boundary I would use**:

> **Do not copy a third-party Udyam website. Do not copy only the first six tabs. Do not treat Udyam as a simple 20-field form.**

The real system is:

**Eligibility → New/Migration/UAP decision → Aadhaar → PAN → enterprise details → ownership/category → units → address → legacy registration → bank → activity → NIC → employment → investment/turnover → government-service preferences → DIC → declarations → final OTP → registration → certificate → login → update/cancel → print/verify/retrieve.**

And the **current MSME thresholds are ₹2.5 Cr / ₹25 Cr / ₹125 Cr investment and ₹10 Cr / ₹100 Cr / ₹500 Cr turnover** for Micro/Small/Medium respectively. ([Udyam Registration][1])

**Official source set:**
[Udyam Home](https://udyamregistration.gov.in/?utm_source=chatgpt.com) · [New Registration](https://udyamregistration.gov.in/UdyamRegistration.aspx?utm_source=chatgpt.com) · [Udyami Login](https://udyamregistration.gov.in/Udyam_Login.aspx?utm_source=chatgpt.com) · [UAM Migration](https://udyamregistration.gov.in/UdyamRegistrationExist.aspx?utm_source=chatgpt.com) · [Assisted Migration](https://udyamregistration.gov.in/Udyam_AssistedMigration.aspx?utm_source=chatgpt.com) · [Forgot Number](https://udyamregistration.gov.in/ForgotRegNo.aspx?utm_source=chatgpt.com) · [Important Rules](https://udyamregistration.gov.in/Important.aspx?utm_source=chatgpt.com) · [Official Udyam Assist Platform](https://udyamassist.gov.in/?utm_source=chatgpt.com) 

[1]: https://www.udyamregistration.gov.in/?open_in_new_tab=true "Udyam Registration : Zero cost, No Fee and Free Registration of MSMEs. This is official website of Govt. of India, Ministry of MSME. No other website/portal/app is official. MSMEs are requested to do MSME Registration here only"
[2]: https://www.udyamregistration.gov.in/UdyamRegistration.aspx "UDYAM REGISTRATION FORM - For New Enterprise who are not Registered yet as MSME"
[3]: https://www.udyamregistration.gov.in/UdyamRegistration.aspx/?utm_source=chatgpt.com "UDYAM REGISTRATION FORM - For New Enterprise who are not Registered yet as MSME"
[4]: https://udyamregistration.gov.in/docs/process_msme_regisration_new_pan_Yes.pdf?utm_source=chatgpt.com "PAN Verification"
[5]: https://udyamregistration.gov.in/docs/UdyamApplication.pdf?utm_source=chatgpt.com "Udyam Registration"
[6]: https://msmedijaipur.gov.in/frontupload/Letter-to-all-DFOs-regarding-FAQ-Udyam-Registration-dated-8-July-2024.pdf?utm_source=chatgpt.com "<table id=\"e1\">"
[7]: https://udyamregistration.gov.in/Udyam_Login.aspx?utm_source=chatgpt.com "Udyami Login"
[8]: https://udyamregistration.gov.in/ForgotRegNo.aspx?utm_source=chatgpt.com "FORGOT - UAM/UDYAM REGISTRATION NUMBER"
[9]: https://www.udyamregistration.gov.in/UdyamRegistrationExist.aspx "Udyam Registration : Zero cost, No Fee and Free Registration of MSMEs. This is official website of Govt. of India, Ministry of MSME. No other website/portal/app is official. MSMEs are requested to do MSME Registration here only"
[10]: https://www.udyamregistration.gov.in/Udyam_AssistedMigration.aspx "Assisted Migration Application"
[11]: https://udyamregistration.gov.in/Circular.aspx?utm_source=chatgpt.com "Udyam Registration : Zero cost, No Fee and Free Registration of MSMEs. This is official website of Govt. of India, Ministry of MSME. No other website/portal/app is official. MSMEs are requested to do MSME Registration here only"
