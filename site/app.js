(() => {
  const AVATAR_COLORS = [
    '#7c3aed', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b',
    '#ef4444', '#ec4899', '#8b5cf6', '#14b8a6', '#f97316',
    '#6366f1', '#84cc16', '#e11d48', '#0891b2', '#a855f7',
  ];

  function hashCode(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    return Math.abs(hash);
  }

  function getAvatarColor(company) {
    return AVATAR_COLORS[hashCode(company) % AVATAR_COLORS.length];
  }

  function timeAgo(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMin = Math.floor(diffMs / 60000);
    const diffHr = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);

    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHr < 24) return `${diffHr}h ago`;
    if (diffDay === 1) return '1 day ago';
    if (diffDay < 30) return `${diffDay} days ago`;
    return date.toLocaleDateString();
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function renderJobs(jobs) {
    const list = document.getElementById('jobs-list');
    if (!jobs.length) {
      list.innerHTML = '<div class="no-results">No jobs match your search.</div>';
      return;
    }

    list.innerHTML = jobs.map(job => {
      const company = escapeHtml(job.company || 'Unknown');
      const initial = company.charAt(0).toUpperCase();
      const color = getAvatarColor(company);
      const title = escapeHtml(job.title || '');
      const location = escapeHtml(job.location || '');
      const detailUrl = job.slug ? `jobs/${encodeURIComponent(job.slug)}.html` : (job.absolute_url || job.url || '#');
      const isExternal = !job.slug;
      const targetAttr = isExternal ? ' target="_blank" rel="noopener noreferrer"' : '';
      const jobDate = job.posted_at || job.first_seen || job.scraped_at;
      const date = timeAgo(jobDate);
      const skillLevel = job.skill_level || '';
      const skillMap = { entry: 'Entry-level', mid: 'Mid-level', senior: 'Senior' };
      const skillText = skillMap[skillLevel] || '';

      // Build meta items: company · salary
      const metaParts = [company];
      if (job.salary) metaParts.push(`<span class="meta-salary">${escapeHtml(job.salary.display)}</span>`);
      const metaLine = metaParts.join('<span class="meta-dot"> · </span>');

      // Logo: use logo_url if available, fallback to avatar
      const logoHtml = job.logo_url
        ? `<img class="job-logo" src="${escapeHtml(job.logo_url)}" alt="${company}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
          + `<div class="job-logo-fallback" style="background-color:${color};display:none">${initial}</div>`
        : `<div class="job-logo-fallback" style="background-color:${color}">${initial}</div>`;

      return `<a href="${escapeHtml(detailUrl)}"${targetAttr} class="job-row">
        <div class="job-row-left">
          <div class="job-logo-wrap">
            ${logoHtml}
          </div>
          <div class="job-row-info">
            <div class="job-row-title">${title}</div>
            <div class="job-row-meta">${metaLine}</div>
          </div>
        </div>
        <div class="job-row-right">
          <div class="job-row-location">${location}</div>
          <div class="job-row-date">${date}</div>
        </div>
      </a>`;
    }).join('');
  }

  function init() {
    fetch('jobs.json')
      .then(r => r.json())
      .then(data => {
        const allJobs = data.jobs || [];
        // Only show active (non-expired) jobs on the homepage
        const jobs = allJobs.filter(j => !j.expired);
        const countEl = document.getElementById('job-count');
        const updatedEl = document.getElementById('last-updated');

        countEl.textContent = `${data.total_jobs || jobs.length} jobs found`;
        updatedEl.textContent = `Updated ${timeAgo(data.last_updated)}`;

        renderJobs(jobs);

        const searchInput = document.getElementById('search');
        searchInput.addEventListener('input', () => {
          const q = searchInput.value.toLowerCase().trim();
          if (!q) {
            renderJobs(jobs);
            countEl.textContent = `${jobs.length} jobs found`;
            return;
          }
          const filtered = jobs.filter(j =>
            (j.title || '').toLowerCase().includes(q) ||
            (j.company || '').toLowerCase().includes(q)
          );
          renderJobs(filtered);
          countEl.textContent = `${filtered.length} of ${jobs.length} jobs`;
        });
      })
      .catch(err => {
        console.error('Failed to load jobs:', err);
        const list = document.getElementById('jobs-list');
        if (!list.querySelector('.job-row')) {
          list.innerHTML =
            '<div class="no-results">Failed to load jobs. Please try again later.</div>';
        }
      });
  }

  document.addEventListener('DOMContentLoaded', init);
})();
