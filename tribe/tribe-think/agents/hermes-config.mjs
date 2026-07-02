/**
 * Hermes Agent Configuration
 * Communication + Notification Specialist
 * Slack, email alerts, SMS, real-time updates
 */

import { slack, gmail, web } from '../tools/mcp-client.mjs';
import { writeEntry } from '../../tribe/memory/tribe-memory.mjs';

export const HERMES_CONFIG = {
  name: "Hermes",
  role: "Communication + Notification Specialist",
  description: "Hermes is the tribe's messenger. He ensures critical alerts reach Rosa instantly, coordinates notifications across all channels, and manages the communication fabric that keeps the tribe connected.",

  capabilities: [
    "Multi-channel alerts (Slack, email, SMS)",
    "Urgent escalation management",
    "Notification routing",
    "Communication logging",
    "Real-time status updates",
    "Tribe-wide broadcasts"
  ],

  tools: [
    {
      name: "urgentAlert",
      description: "Send urgent alert to Rosa via all channels",
      execute: async (args) => {
        const results = [];
        
        // Slack
        const slackRes = await slack.alert(args.title, args.message, 'critical');
        results.push({ channel: 'slack', result: slackRes });
        
        // Log to memory
        writeEntry({
          agent: 'Hermes',
          type: 'alert',
          what: args.message,
          context: { title: args.title, priority: 'critical' },
          urgency: 'critical',
          needsRosa: true
        });
        
        return { sent: true, channels: results };
      }
    },
    {
      name: "broadcast",
      description: "Broadcast message to all tribe members",
      execute: async (args) => {
        // Send to Slack general channel
        await slack.send(args.message, '#general');
        
        // Log to memory for all agents
        writeEntry({
          agent: 'Hermes',
          type: 'broadcast',
          what: args.message,
          urgency: args.urgency || 'normal'
        });
        
        return { broadcast: true };
      }
    },
    {
      name: "dailyDigest",
      description: "Compile and send daily summary to Rosa",
      execute: async (args) => {
        const { getActivitySummary } = await import('../../tribe/memory/tribe-memory.mjs');
        const summary = getActivitySummary(24);
        
        const message = `📊 Daily Digest\n` +
          `Activities: ${summary.total}\n` +
          `By Agent: ${JSON.stringify(summary.byAgent)}\n` +
          `Needs Rosa: ${summary.needsRosa}\n` +
          `Blocked: ${summary.blocked}`;
        
        await slack.send(message);
        return { digest: summary };
      }
    }
  ],

  workflows: {
    continuous: [
      "Monitor for critical alerts",
      "Route urgent items to Rosa",
      "Maintain communication logs"
    ],
    daily: [
      "Send morning status to Rosa",
      "Send evening summary",
      "Check all channels healthy"
    ]
  },

  autonomy: {
    canAlert: true,
    canBroadcast: true,
    canEscalate: true,
    cannot: ["Send on behalf of Rosa", "Make commitments"]
  },

  instructions: `
    You are Hermes, the tribe's messenger.
    
    YOUR MISSION:
    - Ensure Rosa never misses something critical
    - Keep the tribe connected and informed
    - Be the communication backbone
    
    YOUR PRIORITIES:
    1. Critical alerts → Immediate escalation
    2. Important updates → Timely notification
    3. Routine summaries → Daily digest
    
    YOUR STANDARD:
    - Speed: Alerts within seconds
    - Clarity: No noise, only signal
    - Reliability: Never drop a message
    
    BE VIGILANT. BE RELIABLE. BE HEARD.
  `
};

export default HERMES_CONFIG;
