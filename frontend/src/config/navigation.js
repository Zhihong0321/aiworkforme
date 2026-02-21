export const getNavItems = (isPlatformAdmin) => {
  if (isPlatformAdmin) {
    return [
      { label: 'Home', path: '/home', description: 'Quick access dashboard' },
      { label: 'System Settings', path: '/settings', description: 'Platform controls and API keys' },
      { label: 'Message History', path: '/settings/history', description: 'Audit and conversation logs' },
      { label: 'Model Benchmark', path: '/settings/benchmark', description: 'Provider comparison tests' }
    ]
  }

  return [
    { label: 'Home', path: '/home', description: 'Quick access dashboard' },
    { label: 'Playground', path: '/playground', description: 'Test agent interactions' },
    { label: 'My AI Agent', path: '/agents', description: 'Configure your primary agent' },
    { label: 'Inbox', path: '/inbox', description: 'Conversation monitoring' },
    { label: 'Contact Book', path: '/leads', description: 'Lead and customer directory' },
    { label: 'AI Control CRM', path: '/ai-crm', description: 'Automated CRM controls' },
    { label: 'Knowledge', path: '/knowledge', description: 'Knowledge base management' },
    { label: 'Catalog', path: '/catalog', description: 'Products and service catalog' },
    { label: 'Calendar', path: '/calendar', description: 'Schedule and booking view' },
    { label: 'Channel Setup', path: '/channels', description: 'Messaging channel configuration' },
    { label: 'Strategy', path: '/strategy', description: 'AI strategy and policy tuning' },
    { label: 'Analytics', path: '/analytics', description: 'Business and AI metrics' }
  ]
}
