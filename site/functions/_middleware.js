export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (url.hostname === "www.remotepharmacistjobs.com") {
    url.hostname = "remotepharmacistjobs.com";
    return Response.redirect(url.toString(), 301);
  }
  return context.next();
}
