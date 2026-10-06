"""Compare final-manager text only; do not interpret market triggers."""
from .ledger import fingerprint, timestamp
from app.services.ai_report_pdf import extract_portfolio_manager_decision_sections
FIELDS = ('rating','investment_thesis','key_risks','invalidation','next_watch','upgrade','downgrade')
def report_fields(report):
    if isinstance(report.get('fields'),dict): return {k:str(v)[:6000] for k,v in report['fields'].items() if k in FIELDS and v}
    return {k:v for k,v in extract_portfolio_manager_decision_sections(str(report.get('body') or ''))['fields'].items() if k in FIELDS and v}
def report_change(previous_report,current_report):
    if not previous_report or not current_report: return None
    for key in ('assetKey','reportKind','locale'):
        if not previous_report.get(key) or previous_report.get(key) != current_report.get(key): return None
    if any(report.get('status') != 'complete' for report in (previous_report,current_report)): return None
    if not previous_report.get('effectiveDate') or previous_report['effectiveDate'] >= current_report.get('effectiveDate',''): return None
    try:
        if timestamp(previous_report['generatedAt']) >= timestamp(current_report['generatedAt']): return None
    except (ValueError,KeyError): return None
    previous,current = report_fields(previous_report),report_fields(current_report)
    changed = [key for key in FIELDS if previous.get(key) and current.get(key) and ' '.join(previous[key].split()) != ' '.join(current[key].split())]
    if not changed: return None
    return {'fields':changed,'assetKey':current_report['assetKey'],'effectiveDate':current_report['effectiveDate'],'generatedAt':current_report['generatedAt'],'fingerprint':fingerprint({'asset':current_report['assetKey'],'kind':current_report['reportKind'],'locale':current_report['locale'],'date':current_report['effectiveDate'],'fields':{k:current[k] for k in changed}})}
