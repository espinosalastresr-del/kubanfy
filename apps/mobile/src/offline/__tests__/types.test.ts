import type {AudioQuality, DownloadJob} from '../types';

describe('offline types', () => {
  it('quality union', () => {
    const q: AudioQuality = 'medium';
    expect(['low', 'medium', 'lossless']).toContain(q);
  });

  it('download job shape', () => {
    const job: DownloadJob = {
      id: 't:medium',
      trackId: 't',
      title: 'Song',
      quality: 'medium',
      status: 'queued',
      progress: 0,
      createdAt: 1,
      updatedAt: 1,
    };
    expect(job.status).toBe('queued');
  });
});
