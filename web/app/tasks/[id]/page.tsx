import { TaskDetail } from "../../../components/task-detail";
export default async function TaskPage({params}: {params: Promise<{id:string}>}) {
  const {id} = await params;
  return <TaskDetail key={id} id={id}/>;
}
