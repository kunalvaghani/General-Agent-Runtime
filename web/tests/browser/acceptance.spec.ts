import { test, expect } from "@playwright/test";
import { mkdir, readFile, writeFile, access } from "node:fs/promises";
import { join } from "node:path";
import { execFileSync } from "node:child_process";

test("repair a broken project after a real failing test and bounded resume",async({page,request})=>{
  const task=await (await request.post("/api/v1/tasks",{data:{goal:"Repair an intentionally broken Python project",model:"acceptance-model",start:false}})).json();
  await mkdir(task.workspace,{recursive:true});
  await writeFile(join(task.workspace,"addition.py"),"def add(a, b):\n    return a - b\n");
  await writeFile(join(task.workspace,"test_addition.py"),"from addition import add\ndef test_add():\n    assert add(2, 3) == 5\n");
  await page.goto(`/tasks/${task.id}`);await page.getByRole("button",{name:"Resume task"}).click();
  await expect(page.getByRole("heading",{name:"Permission requested"})).toBeVisible();
  await page.getByRole("button",{name:"Approve once"}).click();
  await expect(page.getByTestId("task-status")).toHaveText("BLOCKED");
  const failed=await (await request.get(`/api/v1/tasks/${task.id}/snapshot`)).json();
  expect(failed.task.metadata.execution.observations[0].exit_code).not.toBe(0);
  expect(failed.task.metadata.execution.observations[0].output).toContain("1 failed");
  await page.getByRole("button",{name:"Resume task"}).click();
  await expect(page.getByText("filesystem.write",{exact:true})).toBeVisible();
  expect(await readFile(join(task.workspace,"addition.py"),"utf8")).toContain("a - b");
  await page.getByRole("button",{name:"Approve once"}).click();
  await expect(page.getByText("terminal.run",{exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Approve once"}).click();
  await expect(page.getByTestId("task-status")).toHaveText("COMPLETED");
  expect(await readFile(join(task.workspace,"addition.py"),"utf8")).toContain("a + b");
  const complete=await (await request.get(`/api/v1/tasks/${task.id}/snapshot`)).json();
  expect(complete.task.metadata.execution.retries).toBe(1);
  expect(complete.task.metadata.verification.passed).toBe(true);
});

test("dangerous action cannot run without exact approval and rejection cancels",async({page,request})=>{
  const task=await (await request.post("/api/v1/tasks",{data:{goal:"Dangerous action approval test",model:"acceptance-model"}})).json();
  await page.goto(`/tasks/${task.id}`);await expect(page.getByTestId("task-status")).toHaveText("WAITING APPROVAL");
  const pending=(await (await request.get(`/api/v1/tasks/${task.id}`)).json()).metadata.execution.pending;
  expect((await request.post(`/api/v1/tasks/${task.id}/approve`,{data:{request_id:"wrong-id",approve:true}})).status()).toBe(409);
  await expect(access(join(task.workspace,"danger.txt"))).rejects.toThrow();
  await page.getByRole("button",{name:"Reject",exact:true}).click();
  await expect(page.getByTestId("task-status")).toHaveText("CANCELLED");
  expect((await request.post(`/api/v1/tasks/${task.id}/approve`,{data:{request_id:pending.id,approve:true}})).status()).toBe(409);
  await expect(access(join(task.workspace,"danger.txt"))).rejects.toThrow();
});

for(const scenario of ["malformed-plan","malformed-decision"]) {
  test(`${scenario} fails safely without tool execution`,async({page,request})=>{
    const task=await (await request.post("/api/v1/tasks",{data:{goal:scenario,model:"acceptance-model"}})).json();
    await page.goto(`/tasks/${task.id}`);await expect(page.getByTestId("task-status")).toHaveText("BLOCKED");
    const snapshot=await (await request.get(`/api/v1/tasks/${task.id}/snapshot`)).json();
    expect(snapshot.task.metadata.verification?.passed).not.toBe(true);
    expect(snapshot.task.metadata.execution?.observations??[]).toHaveLength(0);
    if(scenario==="malformed-plan")expect(snapshot.plan).toBeNull();
    await expect(access(join(task.workspace,"addition.py"))).rejects.toThrow();
    await page.getByRole("button",{name:"Cancel task"}).click();
    await expect(page.getByTestId("task-status")).toHaveText("CANCELLED");
  });
}

test("cancel an active Docker task and confirm its container is removed",async({page,request})=>{
  const task=await (await request.post("/api/v1/tasks",{data:{goal:"Cancel active container task",model:"acceptance-model"}})).json();
  await page.goto(`/tasks/${task.id}`);await expect(page.getByTestId("task-status")).toHaveText("WAITING APPROVAL");
  await page.getByRole("button",{name:"Approve once"}).click();
  let container="";
  await expect.poll(async()=>{try{container=(await readFile(join(task.workspace,"started.txt"),"utf8")).trim();return Boolean(container);}catch{return false;}}).toBe(true);
  await expect(page.getByTestId("task-status")).toHaveText("RUNNING");
  await page.getByRole("button",{name:"Cancel task"}).click();
  await expect(page.getByTestId("task-status")).toHaveText("CANCELLED");
  await expect.poll(()=>{try{execFileSync("docker",["inspect",container],{stdio:"pipe"});return false;}catch{return true;}}).toBe(true);
  await expect(access(join(task.workspace,"finished.txt"))).rejects.toThrow();
  await expect(page.getByText("Task event stream finished.")).toBeVisible();
});
