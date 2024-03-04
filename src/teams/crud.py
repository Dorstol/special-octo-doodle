from fastapi import HTTPException, status
from sqlalchemy import select, Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.accounts.crud import get_user_teams
from src.accounts.models import User
from src.teams.models import Team, UserTeam
from src.teams.schemas import TeamCreate, TeamUpdatePartial


async def get_teams(session: AsyncSession) -> list[Team]:
    stmt = select(Team).options(joinedload(Team.members))
    result: Result = await session.execute(stmt)
    teams = result.unique().scalars().all()
    return list(teams)


async def get_team(session: AsyncSession, team_id: int) -> Team | None:
    stmt = select(Team).where(Team.id == team_id).options(joinedload(Team.members))
    result: Result = await session.execute(stmt)
    team = result.unique().scalar_one()
    return team


async def create_team(
    team_in: TeamCreate,
    user_id: int,
    session: AsyncSession,
) -> Team:
    teams = await get_user_teams(user_id=user_id, session=session)
    for team in teams:
        if team.owner_id == user_id and team.status != "Ready":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="CAN`T_CREATE_TEAM"
            )
    team = Team(
        title=team_in.title,
        project_name=team_in.project_name,
        description=team_in.description,
    )
    team.owner_id = user_id
    session.add(team)
    await session.flush()
    user_team = UserTeam(user_id=user_id, team_id=team.id)
    session.add(user_team)
    await session.commit()
    return await get_team(session=session, team_id=team.id)


async def update_team(
    session: AsyncSession,
    team: Team,
    user_id: int,
    team_update: TeamUpdatePartial,
):
    for name, value in team_update.model_dump(exclude_unset=True).items():
        setattr(team, name, value)
    await session.commit()
    return team


async def delete_team(
    session: AsyncSession,
    team: Team,
    user: User,
) -> None:
    await session.delete(team)
    await session.commit()


async def join_team(
    team: Team,
    user: User,
    session: AsyncSession,
):
    if len(team.members) == team.MAX_TEAM_MEMBERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="MAX_MEMBERS"
        )
    if user in team.members:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="ALREADY_IN_TEAM"
        )
    user_team = UserTeam(user_id=user.id, team_id=team.id)
    session.add(user_team)
    await session.commit()
    return user_team


async def leave_team(
    team: Team,
    user: User,
    session: AsyncSession,
) -> None:
    if user and team:
        # if user.id == team.owner_id:
        #     await delete_team(session=session, team=team, user=user)
        if user in team.members:
            team.members.remove(user)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="NOT_TEAM_MEMBER"
            )
    await session.commit()
