/** App URLs shared by features that link to each other's screens (features never import each other). */
export const routes = {
  tender: (tenderId: number) => `/tenders/${tenderId}`,
  fillForm: (formId: number) => `/forms/${formId}/fill`,
  exportForm: (formId: number) => `/forms/${formId}/export`,
};
