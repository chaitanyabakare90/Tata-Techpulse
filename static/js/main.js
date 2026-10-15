/**
 * main.js - AUTOSAR HLD Document Analysis Assistant
 * Global UI helpers and notification handlers
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Bootstrap tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(el => new bootstrap.Tooltip(el));

  // Auto-dismiss alerts after 5 seconds (except warnings/danger)
  const autoAlerts = document.querySelectorAll('.alert-success, .alert-info');
  autoAlerts.forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) {
        bsAlert.close();
      }
    }, 5000);
  });
});
