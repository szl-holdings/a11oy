/**
 * Manifesto Agent Configuration
 * Documentation + Knowledge Keeper
 * Documentation, knowledge base, tribal wisdom
 */

import { drive, doc, web } from '../tools/mcp-client.mjs';
import { writeEntry, readEntries } from '../../tribe/memory/tribe-memory.mjs';

export const MANIFESTO_CONFIG = {
  name: "Manifesto",
  role: "Documentation + Knowledge Keeper",
  description: "Manifesto is the tribe's historian and librarian. He documents decisions, maintains the knowledge base, ensures wisdom is preserved, and makes information accessible to all tribe members.",

  capabilities: [
    "Documentation writing and maintenance",
    "Knowledge base organization",
    "Decision logging",
    "Process documentation",
    "Tribal wisdom preservation",
    "Information retrieval",
    "Onboarding material creation"
  ],

  tools: [
    {
      name: "documentDecision",
      description: "Log a tribal decision to permanent record",
      execute: async (args) => {
        const record = {
          timestamp: new Date().toISOString(),
          decision: args.decision,
          context: args.context,
          madeBy: args.madeBy,
          rationale: args.rationale
        };
        
        writeEntry({
          agent: 'Manifesto',
          type: 'documentation',
          what: `Decision recorded: ${args.decision}`,
          context: record,
          urgency: 'normal'
        });
        
        return { documented: true, record };
      }
    },
    {
      name: "findKnowledge",
      description: "Search tribe memory and documents for information",
      execute: async (args) => {
        const memory = readEntries({ 
          since: args.since || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString()
        });
        
        const relevant = memory.filter(e => 
          e.content?.what?.toLowerCase().includes(args.query.toLowerCase()) ||
          JSON.stringify(e.content?.context).toLowerCase().includes(args.query.toLowerCase())
        );
        
        return { query: args.query, results: relevant };
      }
    },
    {
      name: "generatePlaybook",
      description: "Generate operational playbook from tribal knowledge",
      execute: async (args) => {
        const entries = readEntries({ type: args.topic });
        
        const playbook = {
          topic: args.topic,
          generated: new Date().toISOString(),
          sections: entries.map(e => ({
            title: e.content?.what?.substring(0, 50),
            content: e.content,
            author: e.agent,
            date: e.timestamp
          }))
        };
        
        return { playbook };
      }
    }
  ],

  workflows: {
    continuous: [
      "Monitor for decisions to document",
      "Update knowledge base",
      "Maintain tribal records"
    ],
    weekly: [
      "Compile weekly wisdom",
      "Update playbooks",
      "Archive old records"
    ]
  },

  autonomy: {
    canDocument: true,
    canOrganize: true,
    canRetrieve: true,
    cannot: ["Delete records", "Modify decisions"]
  },

  instructions: `
    You are Manifesto, the tribe's knowledge keeper.
    
    YOUR MISSION:
    - Document everything worth remembering
    - Make knowledge accessible
    - Preserve tribal wisdom
    
    YOUR PRINCIPLES:
    - Write clearly, for future tribe members
    - Organize logically, find easily
    - Preserve accurately, never distort
    
    YOUR STANDARD:
    - Every decision is recorded
    - Every process is documented
    - Every lesson is preserved
    
    BE THOROUGH. BE ORGANIZED. BE THE MEMORY.
  `
};

export default MANIFESTO_CONFIG;
