from aiohttp.web import RouteTableDef, Request


health = RouteTableDef()


@health.get('/health')
async def health_route(req: Request, *args, **kwargs):
  return dict(ok=True)
