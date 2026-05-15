/* Adds the SU-76 project to the pipeline manager's mock data. */

(() => {
  if (!window.PIPELINE_MOCK) return;
  try { window.PIPELINE_MOCK.createProject({ name: 'SU-76', folder: 'su-76', fps: 24, resolution: '2048x858' }); } catch (e) {}
  try { window.PIPELINE_MOCK.createAssetType('su-76', 'vehicle'); } catch (e) {}
  try { window.PIPELINE_MOCK.createAsset('su-76', 'vehicle', 'su_76'); } catch (e) {}
})();
