"""Local finance demo app. Uses sample records, ephemeral keys, and simulated drafts."""
from .api import create_app
from .finance import InvoiceWorkflow

finance_workflow = InvoiceWorkflow()
app = create_app(finance_workflow.gateway, finance_workflow=finance_workflow)
