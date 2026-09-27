"""Synthetic (fictional) supplier proposals for one procurement request.

All companies, people, clients and figures are invented for classroom use.

RFP: Northwind Retail Group - RFP-2026-017
     Customer Data Platform (CDP) & Marketing Automation Implementation
"""

RFP_TITLE = "RFP-2026-017: Customer Data Platform & Marketing Automation Implementation"
BUYER = "Northwind Retail Group"

REQUIREMENT_SUMMARY = (
    "Northwind Retail Group (fictional) operates 180 stores and an e-commerce site across five "
    "countries. It requires a supplier to implement a Customer Data Platform that unifies "
    "roughly 12 million customer profiles from POS, e-commerce, loyalty and the call centre, "
    "integrates with the existing SAP ERP and Salesforce Service Cloud, and activates "
    "personalised journeys across email, SMS and app push, with GDPR-compliant consent management."
)

SUPPLIERS = [
    # ------------------------------------------------------------------ APEX
    {
        "file": "Apex_Systems_Proposal.pdf",
        "name": "Apex Systems",
        "tagline": "Enterprise Data & Integration Engineering",
        "date": "2026-09-10",
        "sections": [
            ("1. Executive Summary", [
                "Apex Systems is pleased to respond to Northwind Retail Group's RFP-2026-017. We "
                "understand that Northwind needs a single, trusted customer view across POS, "
                "e-commerce, loyalty and call-centre data, activated in real time across email, SMS "
                "and push, while meeting GDPR obligations in five countries.",
                "Our proposal prioritises architectural robustness and security. We will deliver a "
                "cloud-native, event-driven CDP that can scale well beyond Northwind's current 12 "
                "million profiles, with enterprise-grade controls independently audited every year. "
                "We recognise that our price is above the market average; it reflects a senior "
                "engineering team and a platform designed to run for ten years without re-platforming.",
            ]),
            ("2. Proposed Solution and Architecture", [
                "The solution uses an event-driven architecture on Microsoft Azure: an Apache Kafka "
                "event backbone ingests POS, web, app and loyalty events with sub-second latency; a "
                "Delta Lake identity layer performs deterministic and probabilistic identity "
                "resolution; and a composable activation layer publishes audiences to email, SMS and "
                "push providers through a managed API gateway.",
                "Integrations: we provide 42 pre-built, versioned connectors, including certified "
                "connectors for SAP S/4HANA (OData and IDoc) and Salesforce Service Cloud "
                "(Platform Events and Bulk API 2.0). All connectors are monitored with automated "
                "replay on failure.",
                "Scalability: the platform auto-scales horizontally and has been load-tested at "
                "50 million profiles and 15,000 events per second with p95 profile-lookup latency "
                "under 120 ms. Infrastructure is defined as code (Terraform) and deployed through "
                "CI/CD pipelines with automated regression tests.",
            ]),
            ("3. Implementation Approach, Timeline and Team", [
                "We follow a four-phase delivery over 7 months (30 weeks). Phases overlap where "
                "dependencies allow; a formal go/no-go gate precedes production cut-over.",
            ]),
            ("TABLE:timeline", [
                ["Phase", "Weeks", "Key milestone"],
                ["1. Discovery & design", "1-6", "Solution design authority sign-off"],
                ["2. Platform build & integrations", "7-18", "SAP and Salesforce connectors live in test"],
                ["3. Journeys, testing & UAT", "19-26", "UAT sign-off, performance test report"],
                ["4. Cut-over & hypercare", "27-30", "Go-live, 30-day hypercare exit"],
            ]),
            ("", [
                "Team: 1 engagement lead, 2 solution architects, 6 data/integration engineers, "
                "1 security architect, 2 QA engineers and 1 project manager (13 FTE at peak). "
                "Key risks (identity-match quality, SAP data quality) are tracked in a risk log "
                "reviewed fortnightly; however, a detailed mitigation plan will be agreed in Phase 1.",
            ]),
            ("4. Commercial Proposal", [
                "Pricing is fixed-price for implementation plus annual subscription and support. "
                "All figures exclude VAT.",
            ]),
            ("TABLE:price", [
                ["Item", "Price (EUR)"],
                ["Implementation (fixed price, 30 weeks)", "780,000"],
                ["Platform licence & Azure hosting, per year", "165,000"],
                ["Support & maintenance, per year", "48,000"],
                ["Total cost of ownership, 3 years", "1,419,000"],
            ]),
            ("", [
                "Assumptions: Northwind provides test data and SAP/Salesforce sandbox access by "
                "week 4; up to 12 journey templates are included; change requests are charged at "
                "EUR 1,250 per consultant day; licence price is held for 3 years.",
            ]),
            ("5. Security, Compliance and Risk Controls", [
                "Apex Systems holds ISO/IEC 27001:2022 certification and an unqualified SOC 2 "
                "Type II report (period ending June 2026), both available under NDA. The solution "
                "is hosted exclusively in EU Azure regions (West Europe, Germany West Central).",
                "Controls include AES-256 encryption at rest, TLS 1.3 in transit, customer-managed "
                "keys in Azure Key Vault, role-based access with SSO and MFA, field-level "
                "pseudonymisation of personal data, and immutable audit logs retained for 7 years "
                "and streamed to Northwind's SIEM.",
                "GDPR: we sign Northwind's Data Processing Agreement, maintain a record of "
                "processing, support automated data-subject access and erasure requests within 72 "
                "hours, and conduct a DPIA with Northwind's DPO in Phase 1. Independent penetration "
                "tests are performed before go-live and annually thereafter.",
            ]),
            ("6. Support Model, Experience and References", [
                "Support is provided 08:00-18:00 CET on business days, with 24x7 on-call cover for "
                "Priority 1 incidents only. P1 response time is 1 hour; P2 is 4 business hours.",
                "Relevant experience: CDP implementations for two European retailers in the last "
                "three years. References: Head of Data, Baltic Home Stores (fictional); CIO, "
                "Lumen Pharmacy Group (fictional). Contact details provided on request after "
                "shortlisting.",
            ]),
        ],
    },
    # ------------------------------------------------------------------ BRIGHTPATH
    {
        "file": "BrightPath_Tech_Proposal.pdf",
        "name": "BrightPath Tech",
        "tagline": "Fast, affordable marketing technology",
        "date": "2026-09-08",
        "sections": [
            ("1. Executive Summary", [
                "BrightPath Tech is excited to submit our proposal for Northwind's CDP and marketing "
                "automation programme. We are a young, agile team and we believe we can deliver the "
                "fastest and most affordable implementation in the market.",
                "We will get Northwind live in just 12 weeks at a total cost that is significantly "
                "lower than traditional system integrators, so that the marketing team can start "
                "running personalised campaigns before the holiday season.",
            ]),
            ("2. Proposed Solution", [
                "We will implement a SaaS CDP (a leading off-the-shelf product) configured with its "
                "standard data model. Customer data from e-commerce and loyalty will be imported "
                "through nightly CSV batch files. POS data can be added in a later phase.",
                "Integration with SAP and Salesforce will use the CDP's standard connectors where "
                "available; custom integration work, if required, is not included in this proposal. "
                "The platform is scalable and cloud based.",
                "Email and SMS journeys will be built using the product's drag-and-drop journey "
                "builder. App push is supported through a third-party plug-in.",
            ]),
            ("3. Implementation Plan and Timeline", [
                "Our accelerated methodology delivers in 12 weeks:",
            ]),
            ("TABLE:timeline", [
                ["Phase", "Weeks", "Milestone"],
                ["Setup & configuration", "1-4", "CDP tenant configured"],
                ["Data import & journeys", "5-9", "First campaigns built"],
                ["Testing & go-live", "10-12", "Go-live"],
            ]),
            ("", [
                "Team: a project lead and three consultants. Additional resources can be added "
                "if needed. A risk plan will be prepared after kick-off.",
            ]),
            ("4. Pricing", [
                "Our pricing is simple and transparent. All prices exclude VAT.",
            ]),
            ("TABLE:price", [
                ["Item", "Price (EUR)"],
                ["Implementation (12 weeks)", "210,000"],
                ["CDP subscription, per year", "115,000"],
                ["Support, per year", "18,000"],
                ["Total cost of ownership, 3 years", "609,000"],
            ]),
            ("", [
                "Assumptions: implementation is time-and-materials capped at the amount above; "
                "subscription pricing is based on 5 million profiles, and additional profiles are "
                "charged at the vendor's list price; POS integration and custom SAP/Salesforce "
                "integration are out of scope.",
            ]),
            ("5. Security and Compliance", [
                "BrightPath follows industry best practices for information security. The CDP "
                "vendor is responsible for platform security and hosting. We are currently working "
                "towards ISO 27001 certification.",
                "We take GDPR seriously and our consultants complete data-protection awareness "
                "training. Data residency and data-processing terms will be confirmed with the "
                "software vendor during contracting.",
            ]),
            ("6. Support and Experience", [
                "After go-live we provide email-based support during business hours (09:00-17:00 "
                "IST), with a target response within one business day.",
                "BrightPath Tech was founded in 2024. Our team has delivered two marketing "
                "automation projects for mid-sized online retailers. References are available "
                "upon request.",
            ]),
        ],
    },
    # ------------------------------------------------------------------ NEXAWORKS
    {
        "file": "NexaWorks_Proposal.pdf",
        "name": "NexaWorks",
        "tagline": "Delivery excellence for customer data programmes",
        "date": "2026-09-09",
        "sections": [
            ("1. Executive Summary and Understanding", [
                "NexaWorks understands that Northwind Retail Group needs to unify about 12 million "
                "customer profiles from POS, e-commerce, loyalty and the call centre; integrate "
                "with SAP ERP and Salesforce Service Cloud; and activate consented, personalised "
                "journeys across email, SMS and app push in five countries.",
                "Our proposal is balanced: a proven composable CDP, a delivery plan built from "
                "14 comparable programmes, a fair fixed price and an operations model designed "
                "around Northwind's trading calendar. Our differentiator is predictable delivery "
                "and long-term support.",
            ]),
            ("2. Proposed Solution", [
                "We propose a composable CDP on Google Cloud (EU region) with a BigQuery-based "
                "unified profile store, near-real-time streaming ingestion for web and app events, "
                "and 15-minute micro-batch ingestion for POS and loyalty. Identity resolution uses "
                "deterministic rules (loyalty ID, email, phone) with a configurable fuzzy-match layer.",
                "Integrations: standard connectors for Salesforce Service Cloud and an SAP "
                "integration built on SAP Integration Suite. The platform supports 25 million "
                "profiles on the proposed tier and scales by upgrading the tier.",
            ]),
            ("3. Implementation Plan, Milestones and Team", [
                "Delivery runs for 22 weeks in five stage-gated phases. Each phase ends with a "
                "documented acceptance criterion signed off by Northwind's product owner.",
            ]),
            ("TABLE:timeline", [
                ["Phase", "Weeks", "Milestone / acceptance criterion"],
                ["0. Mobilisation", "1-2", "Governance, RACI and risk register approved"],
                ["1. Discovery & design", "3-6", "Data model and integration specs signed"],
                ["2. Build (3 sprints)", "7-14", "SAP, Salesforce, POS feeds in test; 95% match rate"],
                ["3. Journeys & UAT", "15-19", "20 journeys pass UAT; performance test passed"],
                ["4. Go-live & hypercare", "20-22", "Staged country roll-out; 90-day hypercare"],
            ]),
            ("", [
                "Team (named in Appendix A): engagement director, delivery manager, solution "
                "architect, 4 data engineers, 2 marketing-automation specialists, QA lead, change "
                "and training lead - 11 FTE at peak, 70% of whom have worked together on at least "
                "three prior programmes. Governance: weekly delivery stand-up, fortnightly steering "
                "committee, monthly executive review.",
                "Risk plan: a live risk register with owners and mitigations. Top risks: (1) SAP data "
                "quality - mitigated by a data-profiling sprint in weeks 3-4; (2) identity match rate "
                "below target - mitigated by tuning cycles with a 95% acceptance gate; (3) peak-season "
                "freeze - go-live scheduled before the November change freeze with a rollback plan "
                "rehearsed in UAT; (4) key-person dependency - named deputies for every lead role.",
            ]),
            ("4. Commercial Proposal", [
                "Fixed-price implementation with milestone-based payments (20/30/30/20). Prices "
                "exclude VAT.",
            ]),
            ("TABLE:price", [
                ["Item", "Price (EUR)"],
                ["Implementation (fixed price, 22 weeks)", "520,000"],
                ["Platform licence & Google Cloud hosting, per year", "118,000"],
                ["Managed support (24x7), per year", "36,000"],
                ["Total cost of ownership, 3 years", "982,000"],
            ]),
            ("", [
                "Assumptions: pricing covers up to 25 million profiles and 20 journeys; Northwind "
                "provides a product owner at 50% allocation; travel is included; change requests "
                "at EUR 950 per day; year-2 and year-3 prices are capped at CPI + 2%.",
            ]),
            ("5. Security, Compliance and Risk Controls", [
                "NexaWorks is ISO/IEC 27001:2022 certified and has completed a SOC 2 Type I "
                "assessment; the SOC 2 Type II audit is scheduled for Q1 2027. Data is hosted in "
                "Google Cloud europe-west3 (Frankfurt).",
                "Controls: encryption at rest and in transit, SSO with MFA, least-privilege roles, "
                "consent and preference centre with per-channel opt-in, automated GDPR "
                "access/erasure workflows, and audit logging of all profile access. We will sign "
                "Northwind's DPA and support a DPIA.",
            ]),
            ("6. Support Model, Experience and References", [
                "Support: 24x7 follow-the-sun service desk (Pune, Lisbon, Toronto) with a dedicated "
                "Technical Account Manager. SLAs: P1 response 15 minutes and restore target 4 hours; "
                "P2 response 1 hour; P3 response 8 hours. Service credits apply when SLAs are missed. "
                "Monthly service reviews and quarterly roadmap sessions are included, together with "
                "a 90-day hypercare period after go-live.",
                "Experience: 14 CDP or marketing-automation programmes since 2019, including six "
                "for multi-country retailers. References (fictional): Director of CRM, Harbor & "
                "Pine Outfitters; VP Digital, Kestrel Supermarkets; Head of Loyalty, Solstice Beauty.",
            ]),
        ],
    },
    # ------------------------------------------------------------------ ORBIT
    {
        "file": "Orbit_Digital_Proposal.pdf",
        "name": "Orbit Digital",
        "tagline": "Retail customer engagement since 2010",
        "date": "2026-09-11",
        "sections": [
            ("1. Executive Summary", [
                "Orbit Digital has specialised in retail customer engagement for more than 15 years. "
                "We have delivered over 60 CRM, loyalty and customer data programmes for retailers "
                "across Europe and Asia, and we understand the pressures of running a multi-country "
                "store and e-commerce estate.",
                "We propose to transform Northwind's customer engagement with a modern CDP and "
                "marketing automation capability, drawing on playbooks refined across our retail "
                "client base.",
            ]),
            ("2. Proposed Solution", [
                "Orbit Digital will deploy a leading enterprise CDP and marketing automation suite, "
                "hosted in the EU. The platform provides a unified customer profile, segmentation, "
                "AI-based recommendations and omnichannel journey orchestration.",
                "Integration approach: the detailed integration architecture for SAP, Salesforce "
                "and the POS estate will be defined during the discovery phase once we have "
                "reviewed Northwind's systems. We anticipate using a combination of APIs and file "
                "transfers as appropriate. Scalability will be assessed during discovery.",
            ]),
            ("3. Implementation Approach and Timeline", [
                "We use our proven Orbit Launch methodology across 26 weeks:",
            ]),
            ("TABLE:timeline", [
                ["Phase", "Weeks", "Milestone"],
                ["Discovery", "1-6", "Discovery report"],
                ["Design & build", "7-18", "Platform configured"],
                ["Test & launch", "19-26", "Launch"],
            ]),
            ("", [
                "Team: an engagement partner, a programme manager, a CRM strategist and a delivery "
                "team sized after discovery (typically 8-10 people). Risks will be managed through "
                "our standard RAID log.",
            ]),
            ("4. Commercial Proposal", [
                "Prices exclude VAT.",
            ]),
            ("TABLE:price", [
                ["Item", "Price (EUR)"],
                ["Discovery (fixed price)", "95,000"],
                ["Design, build & launch (estimate)", "420,000 - 520,000"],
                ["Platform licences, per year", "125,000"],
                ["Managed service, per year", "40,000"],
                ["Indicative total cost of ownership, 3 years", "1,010,000 - 1,110,000"],
            ]),
            ("", [
                "Assumptions: the build estimate will be confirmed after discovery; licence "
                "pricing depends on final profile volumes; integration effort is not yet included "
                "in the estimate and will be quoted separately after discovery.",
            ]),
            ("5. Security and Compliance", [
                "Orbit Digital is ISO/IEC 27001 certified. The proposed platform is hosted in EU "
                "data centres and the software vendor holds SOC 2 Type II. We will sign a GDPR "
                "Data Processing Agreement and apply role-based access controls. Detailed security "
                "controls for integrations will be documented during design.",
            ]),
            ("6. Support Model, Experience and References", [
                "Managed service: 24x5 support desk with 24x7 cover for P1 incidents; P1 response "
                "30 minutes, P2 response 4 hours. A named customer success manager runs quarterly "
                "business reviews.",
                "Experience: 60+ retail engagements since 2010, including CDP implementations for "
                "eleven multi-country retailers in the past five years. Retail NPS from our clients "
                "averages 61.",
                "References (fictional, contactable): CMO, Aurora Department Stores (CDP for 18M "
                "profiles, 7 countries); Head of CRM, Velo Sports Retail (loyalty & CDP, 9 "
                "countries); CDO, Maple & Co Grocers (omnichannel journeys, 4 countries); Digital "
                "Director, Nordlys Fashion (CDP migration, 5 countries).",
            ]),
        ],
    },
]
