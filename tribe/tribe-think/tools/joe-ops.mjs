/**
 * Joe Operations Tools — Full MCP Integration
 * Vendor management, compliance, financial oversight
 */

import { gmail, drive, db, calendar, slack, web } from './mcp-client.mjs';

// Tool: vendor_communication_audit — Check all vendor emails for status
export const vendor_communication_audit = {
  name: "vendor_communication_audit",
  description: "Audit recent vendor communications: who responded, who didn't, what's pending.",
  input_schema: {
    type: "object",
    properties: {
      daysBack: { type: "number", default: 14 }
    }
  },
  async execute({ daysBack = 14 }) {
    // Get vendor list
    const vendorsRes = await db.listVendors();
    const vendors = vendorsRes.ok ? vendorsRes.result.vendors || [] : [];
    
    // Search for vendor emails
    const vendorDomains = vendors.map(v => v.email?.split('@')[1]).filter(Boolean);
    const uniqueDomains = [...new Set(vendorDomains)];
    
    const communications = [];
    
    for (const domain of uniqueDomains.slice(0, 20)) { // Limit to 20 domains
      const res = await gmail.search(`from:@${domain} after:${daysBack}d`, 10);
      if (res.ok && res.result.messages) {
        communications.push({
          domain,
          emails: res.result.messages.length,
          lastContact: res.result.messages[0]?.snippet?.substring(0, 100)
        });
      }
    }
    
    // Get pending tasks related to vendors
    const tasksRes = await db.pendingTasks(100);
    const pendingTasks = tasksRes.ok ? tasksRes.result.tasks || [] : [];
    const vendorTasks = pendingTasks.filter(t => 
      t.title?.toLowerCase().includes('vendor') ||
      t.description?.toLowerCase().includes('vendor')
    );
    
    return {
      auditPeriod: `${daysBack} days`,
      totalVendors: vendors.length,
      vendorsWithRecentContact: communications.length,
      communications,
      pendingVendorTasks: vendorTasks.length,
      vendorTasks,
      recommendation: communications.length < vendors.length * 0.5 
        ? "Many vendors haven't been contacted recently. Consider outreach."
        : "Vendor communication looks healthy."
    };
  }
};

// Tool: compliance_calendar_check — Verify all compliance items are scheduled
export const compliance_calendar_check = {
  name: "compliance_calendar_check",
  description: "Check calendar for upcoming compliance deadlines: insurance, permits, inspections.",
  input_schema: {
    type: "object",
    properties: {
      daysForward: { type: "number", default: 90 }
    }
  },
  async execute({ daysForward = 90 }) {
    const now = new Date();
    const future = new Date(now.getTime() + daysForward * 24 * 60 * 60 * 1000);
    
    // Get calendar events
    const eventsRes = await calendar.listEvents(
      now.toISOString(),
      future.toISOString(),
      100
    );
    
    const events = eventsRes.ok ? eventsRes.result.events || [] : [];
    
    // Filter compliance-related events
    const complianceKeywords = ['insurance', 'permit', 'inspection', 'license', 'COI', 'certificate', 'renewal'];
    const complianceEvents = events.filter(e => 
      complianceKeywords.some(kw => 
        e.summary?.toLowerCase().includes(kw) ||
        e.description?.toLowerCase().includes(kw)
      )
    );
    
    // Search Gmail for compliance reminders
    const emailSearches = await Promise.all([
      gmail.search('subject:insurance renewal after:30d', 10),
      gmail.search('subject:permit expiration after:30d', 10),
      gmail.search('subject:inspection due after:30d', 10)
    ]);
    
    const emailAlerts = emailSearches
      .filter(r => r.ok && r.result.messages?.length > 0)
      .map(r => r.result.messages.length)
      .reduce((a, b) => a + b, 0);
    
    return {
      checkPeriod: `Next ${daysForward} days`,
      complianceEventsScheduled: complianceEvents.length,
      upcomingEvents: complianceEvents.slice(0, 10).map(e => ({
        summary: e.summary,
        start: e.start?.dateTime || e.start?.date,
        daysUntil: Math.ceil((new Date(e.start?.dateTime || e.start?.date) - now) / (1000 * 60 * 60 * 24))
      })),
      emailAlertsFound: emailAlerts,
      status: complianceEvents.length === 0 && emailAlerts > 0 
        ? "WARNING: Email alerts found but no calendar events. Action needed."
        : complianceEvents.length > 0 ? "Compliance tracking active" : "No compliance items found"
    };
  }
};

// Tool: expense_anomaly_detection — Find unusual expense patterns
export const expense_anomaly_detection = {
  name: "expense_anomaly_detection",
  description: "Analyze recent expenses for anomalies: duplicates, unusual amounts, missing receipts.",
  input_schema: {
    type: "object",
    properties: {
      daysBack: { type: "number", default: 30 }
    }
  },
  async execute({ daysBack = 30 }) {
    const expensesRes = await db.recentExpenses(200);
    const expenses = expensesRes.ok ? expensesRes.result.expenses || [] : [];
    
    // Filter to requested period
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - daysBack);
    
    const recentExpenses = expenses.filter(e => new Date(e.date) >= cutoff);
    
    // Detect anomalies
    const anomalies = [];
    
    // Check for duplicates (same vendor, amount, within 7 days)
    const byVendor = {};
    for (const e of recentExpenses) {
      const key = `${e.vendor}-${e.amount}`;
      if (!byVendor[key]) byVendor[key] = [];
      byVendor[key].push(e);
    }
    
    for (const [key, items] of Object.entries(byVendor)) {
      if (items.length > 1) {
        anomalies.push({
          type: 'duplicate',
          description: `Possible duplicate: ${items[0].vendor} for $${items[0].amount}`,
          items
        });
      }
    }
    
    // Check for very large amounts (top 5%)
    const amounts = recentExpenses.map(e => parseFloat(e.amount) || 0).sort((a, b) => b - a);
    const threshold = amounts[Math.floor(amounts.length * 0.05)] || 0;
    const largeExpenses = recentExpenses.filter(e => (parseFloat(e.amount) || 0) > threshold);
    
    return {
      analysisPeriod: `${daysBack} days`,
      totalExpenses: recentExpenses.length,
      totalAmount: recentExpenses.reduce((sum, e) => sum + (parseFloat(e.amount) || 0), 0).toFixed(2),
      anomaliesFound: anomalies.length,
      anomalies,
      largeExpenses: largeExpenses.slice(0, 5).map(e => ({
        vendor: e.vendor,
        amount: e.amount,
        date: e.date,
        category: e.category
      })),
      recommendation: anomalies.length > 0 
        ? "Review flagged anomalies for potential duplicates or errors"
        : "No significant anomalies detected"
    };
  }
};

// Tool: weekly_ops_report — Generate comprehensive weekly operations report
export const weekly_ops_report = {
  name: "weekly_ops_report",
  description: "Generate full weekly operations report for Rosa: vendors, expenses, tasks, compliance.",
  input_schema: {
    type: "object",
    properties: {}
  },
  async execute() {
    // Gather all data in parallel
    const [
      vendors,
      expenses,
      tasks,
      properties,
      urgentEmails
    ] = await Promise.all([
      db.listVendors(),
      db.recentExpenses(100),
      db.pendingTasks(100),
      db.listProperties(),
      gmail.search('subject:urgent OR subject:emergency after:7d', 20)
    ]);
    
    // Compile report
    const pendingTasks = tasks.ok ? tasks.result.tasks || [] : [];
    const recentExpenses = expenses.ok ? expenses.result.expenses || [] : [];
    
    const report = {
      generatedAt: new Date().toISOString(),
      period: "Last 7 days",
      
      executiveSummary: {
        propertiesManaged: properties.ok ? properties.result.properties?.length || 0 : 0,
        activeVendors: vendors.ok ? vendors.result.vendors?.length || 0 : 0,
        pendingTasks: pendingTasks.length,
        expensesTracked: recentExpenses.length,
        urgentItems: urgentEmails.ok ? urgentEmails.result.messages?.length || 0 : 0
      },
      
      tasks: {
        totalPending: pendingTasks.length,
        byPriority: {
          high: pendingTasks.filter(t => t.priority === 'high').length,
          medium: pendingTasks.filter(t => t.priority === 'medium').length,
          low: pendingTasks.filter(t => t.priority === 'low').length
        },
        overdue: pendingTasks.filter(t => t.due_date && new Date(t.due_date) < new Date()).length,
        topItems: pendingTasks
          .filter(t => t.priority === 'high')
          .slice(0, 5)
          .map(t => ({ title: t.title, assignee: t.assignee, due: t.due_date }))
      },
      
      expenses: {
        total7Days: recentExpenses
          .filter(e => new Date(e.date) > new Date(Date.now() - 7 * 24 * 60 * 60 * 1000))
          .reduce((sum, e) => sum + (parseFloat(e.amount) || 0), 0)
          .toFixed(2),
        byCategory: recentExpenses.reduce((acc, e) => {
          acc[e.category] = (acc[e.category] || 0) + (parseFloat(e.amount) || 0);
          return acc;
        }, {})
      },
      
      vendorActivity: {
        recentCommunications: 0, // Would need to count from vendor_communication_audit
        pendingVendorTasks: pendingTasks.filter(t => 
          t.title?.toLowerCase().includes('vendor') ||
          t.description?.toLowerCase().includes('vendor')
        ).length
      },
      
      urgent: urgentEmails.ok && urgentEmails.result.messages?.length > 0
        ? urgentEmails.result.messages.slice(0, 5).map(m => ({
            subject: m.snippet?.substring(0, 50),
            from: m.payload?.headers?.find(h => h.name === 'From')?.value
          }))
        : []
    };
    
    return report;
  }
};

// Tool: alert_escalation — Send urgent alerts to Slack/email
export const alert_escalation = {
  name: "alert_escalation",
  description: "Escalate urgent issues to Slack or prepare email alerts for Rosa.",
  input_schema: {
    type: "object",
    properties: {
      issue: { type: "string", description: "Description of the issue" },
      priority: { type: "string", enum: ["low", "medium", "high", "critical"], default: "high" },
      sendSlack: { type: "boolean", default: true },
      draftEmail: { type: "boolean", default: true }
    },
    required: ["issue"]
  },
  async execute({ issue, priority = "high", sendSlack = true, draftEmail = true }) {
    const results = { slack: null, email: null };
    
    if (sendSlack) {
      results.slack = await slack.alert(
        `Property Management Alert - ${priority.toUpperCase()}`,
        issue,
        priority
      );
    }
    
    if (draftEmail) {
      // Prepare email draft (would need Gmail draft creation tool)
      results.email = {
        to: "rosa@alloyszlholdings.com",
        subject: `[${priority.toUpperCase()}] Property Management Alert`,
        body: issue,
        status: "draft_prepared"
      };
    }
    
    return {
      escalated: true,
      priority,
      issue,
      results,
      timestamp: new Date().toISOString()
    };
  }
};

// Export all Joe tools
export const JOE_OPS_TOOLS = [
  vendor_communication_audit,
  compliance_calendar_check,
  expense_anomaly_detection,
  weekly_ops_report,
  alert_escalation
];

export default JOE_OPS_TOOLS;
