
# AMLens verified AML knowledge annotations
#
# Each annotation must correspond to a real passage
# in the approved document corpus.
#
# These IDs were identified during local retrieval tests.
# Do not label unrelated chunks automatically.

VERIFIED_CHUNKS = {

    "structuring": {
        "RBI_KYC_Master_Direction_p23_structuring_1": {
            "section": (
                "Chapter V - Customer Identification "
                "Procedure (CIP), Paragraph 21(6)"
            )
        }
    },

    # Complete paragraphs added by scripts/add_verified_typology_chunks.py
    # (reviewed 2026-11-24). One typology per chunk.
    "unusual_activity": {
        "RBI_KYC_Master_Direction_p40_unusual_activity_1": {
            "section": (
                "Chapter VI - Customer Due Diligence (CDD) Procedure, "
                "E. On-going Due Diligence, Paragraphs 39 and 40(1)"
            )
        },
        "FIU_Guidance_p10_unusual_activity_1": {
            "section": (
                "4.10 Enhanced Due Diligence (EDD) Norms, 4.10.1"
            )
        },
        "FATF_Recommendations_p73_unusual_activity_1": {
            "section": (
                "Interpretive Note to Recommendation 10 "
                "(Customer Due Diligence), Enhanced CDD measures, "
                "Paragraph 20"
            )
        }
    },

    "rapid_movement": {
        "RBI_KYC_Master_Direction_p40_rapid_movement_1": {
            "section": (
                "Chapter VI - Customer Due Diligence (CDD) Procedure, "
                "E. On-going Due Diligence, Paragraph 40"
            )
        }
    },

    "fan_in_out": {
        "RBI_KYC_Master_Direction_p41_fan_in_out_1": {
            "section": (
                "Chapter VI - Customer Due Diligence (CDD) Procedure, "
                "E. On-going Due Diligence, Paragraph 41(2), Explanation"
            )
        }
    },

    "customer_due_diligence": {
        "RBI_KYC_Master_Direction_p11_c2": {
            "section": (
                "Definitions - Customer Due Diligence (CDD)"
            )
        }
    },

    "enhanced_due_diligence": {
        "FIU_Guidance_p10_c1": {
            "section": (
                "4.10 Enhanced Due Diligence (EDD) Norms"
            )
        }
    },

    "ongoing_monitoring": {
        "RBI_KYC_Master_Direction_p40_c1": {
            "section": (
                "E. On-going Due Diligence"
            )
        }
    },

    "suspicious_transaction_reporting": {
        "FATF_Recommendations_p20_c2": {
            "section": (
                "Recommendation 20 - "
                "Reporting of Suspicious Transactions"
            )
        }
    },

    "money_mules": {
        "RBI_KYC_Master_Direction_p64_c1": {
            "section": (
                "68. Operation of Bank Accounts and Money Mules"
            )
        }
    }
}
