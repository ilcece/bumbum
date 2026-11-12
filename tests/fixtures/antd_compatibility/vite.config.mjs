// 仅用于隔离冒烟，既不加载项目.env，也不连接业务接口。
export default {
  envDir: false,
  plugins: [{
    name: 'synthetic-upload',
    configureServer(server) {
      server.middlewares.use('/_smoke/upload', (req, res) => {
        let bytes = 0;
        req.on('data', chunk => { bytes += chunk.length; });
        req.on('end', () => {
          const send = () => {
            if (res.destroyed) return;
            res.statusCode = req.url.includes('error') ? 500 : 200;
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ ok: res.statusCode === 200, bytes }));
          };
          if (req.url.includes('slow')) setTimeout(send, 1200);
          else send();
        });
      });
    },
  }],
};
