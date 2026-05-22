import { createRouter, createWebHistory } from 'vue-router'

import { listProjects } from '../api/projects'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'workbench',
      component: () => import('../views/HomeView.vue'),
    },
    {
      path: '/health',
      name: 'health',
      component: () => import('../views/HomeView.vue'),
    },
    {
      path: '/projects',
      name: 'projects',
      component: () => import('../views/ProjectList.vue'),
    },
    {
      path: '/maintenance',
      name: 'local-maintenance',
      component: () => import('../views/LocalMaintenance.vue'),
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('../views/AboutView.vue'),
    },
    {
      path: '/help',
      name: 'help',
      component: () => import('../views/HelpView.vue'),
    },
    {
      path: '/getting-started',
      name: 'getting-started',
      component: () => import('../views/GettingStartedView.vue'),
    },
    {
      path: '/templates',
      name: 'templates',
      component: () => import('../views/TemplatesView.vue'),
    },
    {
      path: '/projects/new',
      name: 'project-new',
      component: () => import('../views/ProjectForm.vue'),
    },
    {
      path: '/projects/:id',
      name: 'project-detail',
      component: () => import('../views/ProjectDetail.vue'),
    },
    {
      path: '/projects/:id/settings',
      name: 'project-settings',
      component: () => import('../views/ProjectForm.vue'),
    },
    {
      path: '/projects/:id/calculation-profiles',
      name: 'calculation-profiles',
      component: () => import('../views/CalculationProfiles.vue'),
    },
    {
      path: '/projects/:id/baseline-plans',
      name: 'baseline-plans',
      component: () => import('../views/BaselinePlans.vue'),
    },
    {
      path: '/projects/:id/import',
      name: 'project-import',
      component: () => import('../views/ImportWizard.vue'),
    },
    {
      path: '/projects/:id/dashboard/print',
      name: 'project-dashboard-print',
      component: () => import('../views/DashboardPrintView.vue'),
    },
    {
      path: '/projects/:id/dashboard',
      name: 'project-dashboard',
      alias: '/projects/:id/dashboard-v2',
      component: () => import('../views/DashboardV2View.vue'),
    },
    {
      path: '/projects/:id/progress-items',
      name: 'progress-items',
      alias: '/projects/:id/items',
      component: () => import('../views/ProgressItemsView.vue'),
    },
    {
      path: '/projects/:id/warnings',
      name: 'warnings',
      component: () => import('../views/WarningsView.vue'),
    },
    {
      path: '/projects/:id/rectifications',
      name: 'rectifications',
      component: () => import('../views/RectificationsView.vue'),
    },
    {
      path: '/projects/:id/reports',
      name: 'reports',
      component: () => import('../views/ReportsView.vue'),
    },
    {
      path: '/projects/:id/reports/history',
      name: 'report-history',
      component: () => import('../views/ReportsView.vue'),
    },
    {
      path: '/imports/:batchId/mapping',
      name: 'mapping-confirm',
      component: () => import('../views/MappingConfirm.vue'),
    },
  ],
})

router.beforeEach(async (to) => {
  const projectId = Number(to.params.id)
  if (!to.path.startsWith('/projects/') || !Number.isFinite(projectId) || projectId <= 0) {
    return true
  }

  try {
    const projects = await listProjects()
    const exists = projects.some((project) => project.id === projectId)
    if (exists) {
      localStorage.setItem('currentProjectId', String(projectId))
      return true
    }
    if (localStorage.getItem('currentProjectId') === String(projectId)) {
      localStorage.removeItem('currentProjectId')
    }
    return {
      path: '/projects',
      query: {
        project_missing: String(projectId),
      },
      replace: true,
    }
  } catch {
    return true
  }
})

export default router
