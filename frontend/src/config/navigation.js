export const getNavItems = (isPlatformAdmin) => {
  if (isPlatformAdmin) {
    return [
      { label: 'Home', path: '/home', icon: 'home', description: 'Quick access dashboard' },
      { label: 'System Settings', path: '/settings', icon: 'settings', description: 'Platform controls and API keys' },
      { label: 'Message History', path: '/settings/history', icon: 'history', description: 'Audit and conversation logs' },
      { label: 'Model Benchmark', path: '/settings/benchmark', icon: 'speed', description: 'Provider comparison tests' }
    ]
  }

  return [
    { label: 'Dashboard', path: '/home', icon: 'dashboard', description: 'Quick access dashboard' },
    { label: 'Agents', path: '/agents', icon: 'smart_toy', description: 'List agents and open their dashboards' },
    { label: 'Playground', path: '/playground', icon: 'science', description: 'Test agent interactions' },
    { label: 'CRM AI', path: '/ai-crm', icon: 'smart_toy', description: 'Automated CRM controls' },
    { label: 'Catalog', path: '/catalog', icon: 'storefront', description: 'Products and service catalog' },
    { label: 'Calendar', path: '/calendar', icon: 'calendar_month', description: 'Schedule and booking view' },
    { label: 'Channel Setup', path: '/channels', icon: 'hub', description: 'Messaging channel configuration' },
    { label: 'Strategy', path: '/strategy', icon: 'strategy', description: 'AI strategy and policy tuning' },
    { label: 'Analytics', path: '/analytics', icon: 'analytics', description: 'Business and AI metrics' }
  ]
}
