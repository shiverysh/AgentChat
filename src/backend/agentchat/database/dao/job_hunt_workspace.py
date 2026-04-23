from sqlmodel import desc, select, delete, func

from agentchat.database.models.job_hunt_workspace import JobHuntWorkspaceItem
from agentchat.database.session import async_session_getter


class JobHuntWorkspaceDao:
    @classmethod
    async def create_item(cls, item: JobHuntWorkspaceItem) -> JobHuntWorkspaceItem:
        async with async_session_getter() as session:
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

    @classmethod
    async def list_items_by_user(cls, user_id: str, limit: int = 30) -> list[JobHuntWorkspaceItem]:
        async with async_session_getter() as session:
            statement = (
                select(JobHuntWorkspaceItem)
                .where(JobHuntWorkspaceItem.user_id == user_id)
                .order_by(desc(JobHuntWorkspaceItem.create_time))
                .limit(limit)
            )
            result = await session.exec(statement)
            return result.all()

    @classmethod
    async def count_items_by_user(cls, user_id: str) -> int:
        async with async_session_getter() as session:
            statement = select(func.count()).select_from(JobHuntWorkspaceItem).where(
                JobHuntWorkspaceItem.user_id == user_id
            )
            result = await session.exec(statement)
            return int(result.one() or 0)

    @classmethod
    async def delete_item(cls, item_id: str, user_id: str) -> None:
        async with async_session_getter() as session:
            statement = delete(JobHuntWorkspaceItem).where(
                JobHuntWorkspaceItem.id == item_id,
                JobHuntWorkspaceItem.user_id == user_id,
            )
            await session.exec(statement)
            await session.commit()
