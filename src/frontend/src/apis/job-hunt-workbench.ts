import { request } from '../utils/request'

export function getJobHuntWorkbenchAPI(limit = 24) {
  return request({
    url: '/api/v1/job_hunt/workbench',
    method: 'GET',
    params: { limit },
  })
}

export function deleteJobHuntWorkbenchItemAPI(itemId: string) {
  return request({
    url: `/api/v1/job_hunt/workbench/${itemId}`,
    method: 'DELETE',
  })
}
