"""Dependency-free member marketplace page."""

# The inline HTML/CSS/JavaScript is shipped as one package-safe string.
# ruff: noqa: E501

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Shared Capability Marketplace</title>
<style>
body{font:16px system-ui;margin:0;background:#f5f7fb;color:#172033}main{max-width:1080px;margin:auto;padding:32px}
header,section{background:white;border:1px solid #dce2ea;border-radius:14px;padding:20px;margin-bottom:18px}
label{display:block;font-weight:650;margin-bottom:8px}input{padding:10px;width:min(420px,90%)}button{padding:8px 12px;margin-left:8px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #e7ebf0}.muted{color:#5e6a7e}.links a{margin-right:12px}
</style></head>
<body><main><header><h1>Shared Capability Marketplace</h1>
<p class="muted">Discover governed capabilities. Agent Add-on selection does not grant execution permission. Applications remain external products and are never installed into the Agent or Bridge.</p>
<p id="status">Sign in to the shared platform to open a member session.</p></header>
<section><h2>Agent Add-ons</h2>
<p class="muted">Choose which published Workflow, Skill, Knowledge or Agent profile version this bound Bridge may synchronize.</p>
<label for="bridge">Bridge ID</label><input id="bridge" autocomplete="off"><button id="load">Load marketplace</button>
<table><thead><tr><th>Add-on</th><th>Kind</th><th>Owner</th><th>Visibility</th><th>Selection</th></tr></thead><tbody id="rows"></tbody></table></section>
<section><h2>Applications</h2>
<p class="muted">Independent Software products with their own deployment and update lifecycle. Links open declared integration points; no package is installed here.</p>
<p id="application-status" class="muted">Sign in to discover Applications.</p>
<table><thead><tr><th>Application</th><th>Owner</th><th>Repository</th><th>Release</th><th>Integrations</th></tr></thead><tbody id="application-rows"></tbody></table></section>
</main><script>
const params=new URLSearchParams(location.hash.slice(1));let bearer=params.get("session")||"";const invitation=params.get("invitation")||"";
if(location.hash)history.replaceState(null,"",location.pathname);
async function call(path,body){const response=await fetch(path,{method:"POST",headers:{"Authorization":"Bearer "+bearer,"Content-Type":"application/json"},body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw new Error(data.code||"request_failed");return data}
function integrationLinks(integrations){const span=document.createElement("span");span.className="links";for(const item of integrations){if(item.kind==="web_ui"&&item.url){const link=document.createElement("a");link.href=item.url;link.target="_blank";link.rel="noopener noreferrer";link.textContent=item.name;span.append(link)}else{const label=document.createElement("span");label.textContent=`${item.name} (${item.kind}) `;span.append(label)}}return span}
async function loadApplications(){const status=document.querySelector("#application-status");if(!bearer){status.textContent="Sign in to discover Applications.";return}try{const data=await call("/v1/member/applications",{});const rows=document.querySelector("#application-rows");rows.textContent="";for(const app of data.applications){const id=app.identity;const tr=document.createElement("tr");for(const value of [`${id.namespace}/${id.name}@${id.version}`,app.owner,`${app.repository_provider}:${app.repository_locator}`,app.release_ref]){const td=document.createElement("td");td.textContent=value;tr.append(td)}const integrations=document.createElement("td");integrations.append(integrationLinks(app.integrations));tr.append(integrations);rows.append(tr)}status.textContent=`${data.applications.length} Application(s); discovery is read-only.`}catch(error){status.textContent=`Applications unavailable: ${error.message}`}}
async function signIn(){if(!invitation){if(bearer)await loadApplications();return}const response=await fetch("/v1/member/sign-in",{method:"POST",headers:{"Authorization":"Invitation "+invitation}});const data=await response.json();if(!response.ok){document.querySelector("#status").textContent="Sign in failed: "+(data.code||"request_failed");return}bearer=data.session;document.querySelector("#status").textContent="Signed in. Enter the Bridge ID to manage Agent Add-ons; Applications are ready below.";await loadApplications()}
async function loadAddons(){const bridge=document.querySelector("#bridge").value.trim();const status=document.querySelector("#status");if(!bearer){status.textContent="Sign in to the shared platform to open a member session.";return}if(!bridge){status.textContent="Enter the bound Bridge ID to load Agent Add-ons.";await loadApplications();return}try{const data=await call("/v1/member/catalog",{bridge_id:bridge});const rows=document.querySelector("#rows");rows.textContent="";for(const entry of data.entries){const id=entry.package.metadata.identity;const current=data.entries.find(other=>other.selected&&other.package.kind===entry.package.kind&&other.package.metadata.identity.namespace===id.namespace&&other.package.metadata.identity.name===id.name);const tr=document.createElement("tr");const button=document.createElement("button");button.textContent=entry.selected?"Revoke":current?"Switch":"Select";button.onclick=async()=>{if(entry.selected){await call("/v1/member/revoke",{bridge_id:bridge,asset:id})}else if(current){await call("/v1/member/replace",{bridge_id:bridge,current:current.package.metadata.identity,replacement:id})}else{await call("/v1/member/select",{bridge_id:bridge,asset:id})}await loadAddons()};for(const value of [`${id.namespace}/${id.name}@${id.version}`,entry.package.kind,`${entry.package.metadata.owner.type}:${entry.package.metadata.owner.id}`,entry.package.metadata.visibility]){const td=document.createElement("td");td.textContent=value;tr.append(td)}const action=document.createElement("td");action.append(button);tr.append(action);rows.append(tr)}status.textContent=`${data.entries.length} Agent Add-on(s)`}catch(error){status.textContent=`Unavailable: ${error.message}`}await loadApplications()}
document.querySelector("#load").onclick=loadAddons;
void signIn();
</script></body></html>"""
