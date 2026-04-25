KEYWORD_PERFORMANCE_QUERY = """
    SELECT
        ad_group_criterion.resource_name,
        ad_group_criterion.keyword.text,
        ad_group_criterion.keyword.match_type,
        ad_group_criterion.cpc_bid_micros,
        ad_group_criterion.status,
        ad_group.resource_name,
        ad_group.name,
        campaign.resource_name,
        campaign.name,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions,
        metrics.ctr,
        metrics.average_cpc
    FROM keyword_view
    WHERE segments.date DURING {date_range}
      AND ad_group_criterion.status != 'REMOVED'
      AND campaign.status != 'REMOVED'
"""

CAMPAIGN_PERFORMANCE_QUERY = """
    SELECT
        campaign.resource_name,
        campaign.id,
        campaign.name,
        campaign.status,
        campaign.serving_status,
        campaign_budget.resource_name,
        campaign_budget.amount_micros,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions,
        metrics.ctr,
        metrics.average_cpc
    FROM campaign
    WHERE segments.date DURING {date_range}
      AND campaign.status != 'REMOVED'
"""

CAMPAIGN_BUDGET_QUERY = """
    SELECT
        campaign.resource_name,
        campaign.id,
        campaign.name,
        campaign.status,
        campaign_budget.resource_name,
        campaign_budget.amount_micros,
        metrics.cost_micros
    FROM campaign
    WHERE segments.date DURING THIS_MONTH
      AND campaign.status != 'REMOVED'
"""

DEVICE_PERFORMANCE_QUERY = """
    SELECT
        campaign.resource_name,
        campaign.name,
        segments.device,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions,
        metrics.ctr
    FROM campaign
    WHERE segments.date DURING {date_range}
      AND campaign.status != 'REMOVED'
"""

HOURLY_PERFORMANCE_QUERY = """
    SELECT
        campaign.resource_name,
        campaign.name,
        segments.hour,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions
    FROM campaign
    WHERE segments.date = '{date}'
      AND campaign.status != 'REMOVED'
"""

ACCOUNT_SUMMARY_QUERY = """
    SELECT
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions,
        metrics.ctr,
        metrics.average_cpc
    FROM customer
    WHERE segments.date DURING {date_range}
"""

SEARCH_TERMS_QUERY = """
    SELECT
        search_term_view.search_term,
        search_term_view.status,
        ad_group.resource_name,
        ad_group.name,
        campaign.resource_name,
        campaign.name,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions,
        metrics.ctr,
        metrics.average_cpc
    FROM search_term_view
    WHERE segments.date DURING {date_range}
      AND metrics.clicks >= 1
      AND campaign.status != 'REMOVED'
"""

QUALITY_SCORE_QUERY = """
    SELECT
        ad_group_criterion.resource_name,
        ad_group_criterion.keyword.text,
        ad_group_criterion.keyword.match_type,
        ad_group_criterion.cpc_bid_micros,
        ad_group_criterion.status,
        ad_group_criterion.quality_info.quality_score,
        ad_group_criterion.quality_info.creative_quality_score,
        ad_group_criterion.quality_info.post_click_quality_score,
        ad_group_criterion.quality_info.search_predicted_ctr,
        ad_group.resource_name,
        ad_group.name,
        campaign.resource_name,
        campaign.name,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions,
        metrics.impressions
    FROM ad_group_criterion
    WHERE ad_group_criterion.type = 'KEYWORD'
      AND ad_group_criterion.status != 'REMOVED'
      AND campaign.status != 'REMOVED'
      AND segments.date DURING LAST_7_DAYS
"""

KEYWORD_HOURLY_QUERY = """
    SELECT
        ad_group_criterion.resource_name,
        ad_group_criterion.keyword.text,
        ad_group_criterion.keyword.match_type,
        ad_group_criterion.cpc_bid_micros,
        segments.hour,
        segments.day_of_week,
        segments.device,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions,
        metrics.ctr,
        metrics.average_cpc
    FROM keyword_view
    WHERE segments.date DURING {date_range}
      AND ad_group_criterion.status != 'REMOVED'
      AND campaign.status != 'REMOVED'
      AND metrics.impressions >= 1
"""
