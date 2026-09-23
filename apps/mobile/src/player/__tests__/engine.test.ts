describe('trackPlayerService fallback', () => {
  it('exports setup and play helpers', () => {
    const mod = require('../trackPlayerService');
    expect(typeof mod.setupPlayerEngine).toBe('function');
    expect(typeof mod.enginePlay).toBe('function');
    expect(typeof mod.enginePause).toBe('function');
  });
});
